from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.local_data.importer import bootstrap_tdx_daily, count_tdx_day_files
from app.local_data.repository import LocalMarketRepository
from app.local_data.tdx_sector import import_tdx_local_metadata


CHINA_TZ = ZoneInfo("Asia/Shanghai")
TDX_ACTION = "请打开并登录通达信终端，下载日线数据后重新同步。"
TDX_ROOT_ACTION = (
    "请先配置 ALPHAAGENTS_TDX_ROOT，并确认通达信终端已打开、已登录、已下载日线数据。"
)
TDX_METADATA_ACTION = "请打开通达信终端并刷新本地行情/板块资料，然后重新同步本地通达信数据。"


class DataSyncService:
    def __init__(
        self,
        *,
        data_db: str | Path,
        tdx_root: str | Path = "",
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.data_db = Path(data_db)
        self.tdx_root = Path(tdx_root) if str(tdx_root) else None
        self.now_provider = now_provider or _now_china

    def status(self) -> dict[str, Any]:
        repository = LocalMarketRepository(self.data_db)
        market_status = repository.status()
        freshness = self._freshness(market_status)
        return {
            "source": "local_tdx",
            "status": "success" if freshness["is_fresh"] else "action_required",
            "market_status": market_status,
            "freshness": freshness,
            "progress": [
                self._daily_status_stage(),
                self._metadata_status_stage(),
                self._freshness_stage(freshness),
            ],
        }

    def sync_all(self) -> dict[str, Any]:
        progress: list[dict[str, str]] = []
        daily_result: dict[str, Any] | None = None
        metadata_result: dict[str, int] | None = None

        if self.tdx_root is None:
            progress.append(
                _stage(
                    "daily_bars",
                    "同步日线行情",
                    "action_required",
                    "未配置通达信数据目录。",
                    action=TDX_ROOT_ACTION,
                )
            )
        elif not self.tdx_root.exists():
            progress.append(
                _stage(
                    "daily_bars",
                    "同步日线行情",
                    "action_required",
                    f"通达信目录不存在：{self.tdx_root}",
                    action=TDX_ROOT_ACTION,
                )
            )
        else:
            total_files = count_tdx_day_files(self.tdx_root)
            pre_sync_status = LocalMarketRepository(self.data_db).status()
            pre_sync_freshness = self._freshness(pre_sync_status)
            if pre_sync_freshness["is_fresh"]:
                daily_result = {
                    "status": "skipped",
                    "reason": "fresh",
                    "total_files": total_files,
                    "imported_files": 0,
                    "imported_bars": 0,
                    "latest_trade_date": pre_sync_freshness["latest_trade_date"],
                    "expected_latest_trade_date": pre_sync_freshness[
                        "expected_latest_trade_date"
                    ],
                }
                progress.append(
                    _stage(
                        "daily_bars",
                        "同步日线行情",
                        "skipped",
                        f"本地日线数据已达到当前预期交易日，已跳过全量导入。通达信目录共有 {total_files} 个日线文件。",
                    )
                )
            else:
                try:
                    daily_result = bootstrap_tdx_daily(
                        tdx_root=self.tdx_root,
                        db_path=self.data_db,
                    )
                    progress.append(
                        _stage(
                            "daily_bars",
                            "同步日线行情",
                            "completed",
                            f"已导入 {daily_result['imported_files']}/{daily_result['total_files']} 个文件，{daily_result['imported_bars']} 条日线。",
                        )
                    )
                except Exception as exc:
                    progress.append(
                        _stage(
                            "daily_bars",
                            "同步日线行情",
                            "failed",
                            f"日线同步失败：{exc}",
                            action=TDX_ACTION,
                        )
                    )

        metadata_stage, metadata_result = self._sync_metadata()
        progress.append(metadata_stage)

        repository = LocalMarketRepository(self.data_db)
        market_status = repository.status()
        freshness = self._freshness(market_status)
        progress.append(self._freshness_stage(freshness))

        failed = any(stage["status"] == "failed" for stage in progress)
        action_required = any(stage["status"] == "action_required" for stage in progress)
        status = "failed" if failed else "action_required" if action_required else "success"

        return {
            "source": "local_tdx",
            "status": status,
            "daily_bars": daily_result,
            "metadata": metadata_result,
            "market_status": market_status,
            "freshness": freshness,
            "progress": progress,
        }

    def _sync_metadata(self) -> tuple[dict[str, str], dict[str, int] | None]:
        if self.tdx_root is None:
            return (
                _stage(
                    "tdx_metadata",
                    "同步股票和板块元数据",
                    "action_required",
                    "未配置通达信数据目录，无法读取本地行业、板块和概念数据。",
                    action=TDX_ROOT_ACTION,
                ),
                None,
            )
        if not self.tdx_root.exists():
            return (
                _stage(
                    "tdx_metadata",
                    "同步股票和板块元数据",
                    "action_required",
                    f"通达信目录不存在：{self.tdx_root}",
                    action=TDX_ROOT_ACTION,
                ),
                None,
            )

        repository = LocalMarketRepository(self.data_db)
        try:
            report = import_tdx_local_metadata(self.tdx_root, repository)
            repository.record_import_run(
                source="tdx_metadata",
                status="success",
                tdx_root=str(self.tdx_root),
                imported_files=1,
                imported_bars=0,
                message=json.dumps(report, ensure_ascii=False),
            )
        except Exception as exc:
            return (
                _stage(
                    "tdx_metadata",
                    "同步股票和板块元数据",
                    "failed",
                    f"通达信本地元数据同步失败：{exc}",
                    action=TDX_METADATA_ACTION,
                ),
                None,
            )

        return (
            _stage(
                "tdx_metadata",
                "同步股票和板块元数据",
                "completed",
                f"已导入 {report['sectors']} 个行业/板块/概念、{report['sector_members']} 条成分关系。",
            ),
            report,
        )

    def _freshness(self, market_status: dict[str, Any]) -> dict[str, Any]:
        current_time = self.now_provider().astimezone(CHINA_TZ)
        expected_trade_date = expected_latest_trade_date(current_time)
        latest_trade_date = market_status.get("latest_trade_date")
        is_fresh = bool(latest_trade_date and latest_trade_date >= expected_trade_date)
        message = (
            "本地日线数据已达到当前预期交易日。"
            if is_fresh
            else f"本地日线最新交易日为 {latest_trade_date or '无'}，预期至少为 {expected_trade_date}。"
        )
        return {
            "current_time": current_time.isoformat(timespec="seconds"),
            "expected_latest_trade_date": expected_trade_date,
            "latest_trade_date": latest_trade_date,
            "is_fresh": is_fresh,
            "message": message,
        }

    def _daily_status_stage(self) -> dict[str, str]:
        if self.tdx_root is None:
            return _stage(
                "daily_bars",
                "同步日线行情",
                "action_required",
                "未配置通达信数据目录。",
                action=TDX_ROOT_ACTION,
            )
        if not self.tdx_root.exists():
            return _stage(
                "daily_bars",
                "同步日线行情",
                "action_required",
                f"通达信目录不存在：{self.tdx_root}",
                action=TDX_ROOT_ACTION,
            )
        return _stage("daily_bars", "同步日线行情", "ready", f"通达信目录已配置：{self.tdx_root}")

    def _metadata_status_stage(self) -> dict[str, str]:
        if self.tdx_root is None:
            return _stage(
                "tdx_metadata",
                "同步股票和板块元数据",
                "action_required",
                "未配置通达信数据目录，无法读取本地行业、板块和概念数据。",
                action=TDX_ROOT_ACTION,
            )
        if not self.tdx_root.exists():
            return _stage(
                "tdx_metadata",
                "同步股票和板块元数据",
                "action_required",
                f"通达信目录不存在：{self.tdx_root}",
                action=TDX_ROOT_ACTION,
            )
        return _stage(
            "tdx_metadata",
            "同步股票和板块元数据",
            "ready",
            f"通达信本地行业、板块和概念数据目录已配置：{self.tdx_root}",
        )

    def _freshness_stage(self, freshness: dict[str, Any]) -> dict[str, str]:
        if freshness["is_fresh"]:
            return _stage("freshness_check", "核对数据新鲜度", "completed", freshness["message"])
        return _stage(
            "freshness_check",
            "核对数据新鲜度",
            "action_required",
            freshness["message"],
            action=TDX_ACTION,
        )


def expected_latest_trade_date(current_time: datetime) -> str:
    local_time = current_time.astimezone(CHINA_TZ)
    candidate = local_time.date()
    if local_time.weekday() < 5 and local_time.time() < time(16, 0):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def _now_china() -> datetime:
    return datetime.now(CHINA_TZ)


def _stage(
    stage: str,
    label: str,
    status: str,
    message: str,
    *,
    action: str = "",
) -> dict[str, str]:
    return {
        "stage": stage,
        "label": label,
        "status": status,
        "message": message,
        "action": action,
    }
