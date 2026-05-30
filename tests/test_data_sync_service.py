from datetime import datetime
from zoneinfo import ZoneInfo

from app.local_data.data_sync import DataSyncService
from app.local_data.repository import LocalMarketRepository


def _bar(trade_date: str) -> dict:
    return {
        "trade_date": trade_date,
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "amount": 123.0,
        "volume": 456,
    }


def _now(value: str):
    fixed = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return lambda: fixed


def test_data_sync_status_treats_friday_data_as_fresh_on_weekend(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_daily_bars("000001.SH", [_bar("2026-05-15")])
    service = DataSyncService(
        data_db=db_path,
        now_provider=_now("2026-05-17T10:00:00"),
    )

    status = service.status()

    assert status["freshness"]["current_time"].startswith("2026-05-17T10:00:00")
    assert status["freshness"]["expected_latest_trade_date"] == "2026-05-15"
    assert status["freshness"]["latest_trade_date"] == "2026-05-15"
    assert status["freshness"]["is_fresh"] is True
    assert status["progress"][-1]["status"] == "completed"


def test_data_sync_status_guides_user_when_local_data_is_stale(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_daily_bars("000001.SH", [_bar("2026-05-14")])
    service = DataSyncService(
        data_db=db_path,
        tdx_root=tmp_path / "new_tdx_mock",
        now_provider=_now("2026-05-17T10:00:00"),
    )

    status = service.status()

    assert status["freshness"]["expected_latest_trade_date"] == "2026-05-15"
    assert status["freshness"]["is_fresh"] is False
    assert status["progress"][-1]["status"] == "action_required"
    assert "通达信终端" in status["progress"][-1]["action"]
    assert "登录" in status["progress"][-1]["action"]
    assert "下载日线" in status["progress"][-1]["action"]


def test_data_sync_run_skips_daily_import_when_local_data_is_already_fresh(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "alphaagents.db"
    tdx_root = tmp_path / "new_tdx_mock"
    tdx_root.mkdir()
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_daily_bars("000001.SH", [_bar("2026-05-15")])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("fresh local data should not trigger full daily import")

    monkeypatch.setattr("app.local_data.data_sync.bootstrap_tdx_daily", fail_if_called)
    service = DataSyncService(
        data_db=db_path,
        tdx_root=tdx_root,
        now_provider=_now("2026-05-17T10:00:00"),
    )

    result = service.sync_all()

    assert result["status"] == "success"
    assert result["daily_bars"]["status"] == "skipped"
    assert result["progress"][0]["status"] == "skipped"
    assert "已达到当前预期交易日" in result["progress"][0]["message"]
