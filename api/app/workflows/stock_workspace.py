from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.domain.enums import DepositionStatus
from app.domain.models import StockTrackingState, StockWorkspace
from app.local_data.repository import LocalMarketDataUnavailable, LocalMarketRepository
from app.repositories.sqlite import SQLiteWorkflowRepository


class StockWorkspaceService:
    def __init__(
        self,
        workflow_repository: SQLiteWorkflowRepository | None = None,
        market_repository: LocalMarketRepository | None = None,
    ) -> None:
        settings = get_settings()
        self.workflow_repository = workflow_repository or SQLiteWorkflowRepository(
            settings.workflow_db
        )
        self.market_repository = market_repository or LocalMarketRepository(settings.data_db)

    def get_workspace(self, symbol: str) -> dict[str, object]:
        normalized_symbol = normalize_market_symbol(symbol)
        data_gaps: list[str] = []
        bars = self._daily_bars(normalized_symbol, data_gaps)
        latest_bar = bars[-1] if bars else None
        selection_result = self.workflow_repository.get_latest_selection_result_for_symbol(
            normalized_symbol
        )
        holding_position = self.workflow_repository.get_position_for_symbol(normalized_symbol)
        holding_result = self.workflow_repository.get_holding_result_for_symbol(
            normalized_symbol
        )
        latest_report = self.workflow_repository.get_latest_research_report(normalized_symbol)
        operations = self.workflow_repository.list_operation_records_for_symbol(
            normalized_symbol
        )
        review_cases = self.workflow_repository.list_review_cases_for_symbol(
            normalized_symbol
        )
        deposition_candidates = (
            self.workflow_repository.list_deposition_candidates_for_symbol(
                normalized_symbol
            )
        )

        if selection_result is None:
            data_gaps.append("latest_selection_result: 当前股票暂无最近选股命中记录")
        if latest_report is None:
            data_gaps.append("latest_research_report: 当前股票暂无研究报告")
        if holding_position is None:
            data_gaps.append("holding_position: 当前股票不在手动持仓中")

        workspace = StockWorkspace(
            symbol=normalized_symbol,
            name=self._security_name(normalized_symbol, selection_result, latest_report),
            latest_bar=latest_bar,
            selection_result=selection_result,
            holding_position=holding_position,
            holding_result=holding_result,
            latest_research_report=latest_report,
            operation_records=operations,
            review_cases=review_cases,
            deposition_candidates=deposition_candidates,
            tracking_state=StockTrackingState.model_validate(
                self.workflow_repository.get_tracking_state(normalized_symbol)
            ),
            data_gaps=data_gaps,
        )
        return workspace.model_dump(mode="json")

    def append_operation(
        self,
        symbol: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        normalized_symbol = normalize_market_symbol(symbol)
        operation_date = payload.get("operation_date") or datetime.now(UTC).date()
        record = self.workflow_repository.append_operation_record(
            operation_date,
            {**payload, "symbol": normalized_symbol},
        )
        return record

    def append_review(
        self,
        symbol: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        normalized_symbol = normalize_market_symbol(symbol)
        review_date = payload.get("review_date") or datetime.now(UTC).date()
        review_case = self.workflow_repository.append_review_case(
            review_date,
            {
                **payload,
                "symbol": normalized_symbol,
                "name": payload.get("name") or self._security_name(normalized_symbol),
            },
        )
        return review_case

    def append_deposition(
        self,
        symbol: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        normalized_symbol = normalize_market_symbol(symbol)
        candidate = self.workflow_repository.save_stock_deposition_candidate(
            normalized_symbol,
            {
                "id": payload.get("id") or str(uuid4()),
                "symbol": normalized_symbol,
                "review_case_id": str(payload.get("review_case_id") or ""),
                "kind": payload.get("kind") or "模式识别",
                "title": payload["title"],
                "content": payload["content"],
                "source": payload.get("source")
                or f"{normalized_symbol} 个股复盘",
                "status": payload.get("status") or DepositionStatus.PENDING.value,
            },
        )
        return candidate

    def update_tracking(
        self,
        symbol: str,
        status: str,
        note: str = "",
    ) -> dict[str, object]:
        return self.workflow_repository.save_tracking_state(
            normalize_market_symbol(symbol),
            status=status,
            note=note,
        )

    def _daily_bars(self, symbol: str, data_gaps: list[str]) -> list[dict[str, Any]]:
        try:
            bars = self.market_repository.get_daily_bars(symbol, limit=2)
        except LocalMarketDataUnavailable as exc:
            data_gaps.append(f"local_daily_bars: {exc}")
            return []
        if not bars:
            data_gaps.append("local_daily_bars: 当前股票暂无本地日线数据")
        return bars

    def _security_name(
        self,
        symbol: str,
        selection_result: dict[str, object] | None = None,
        latest_report: dict[str, object] | None = None,
    ) -> str:
        if latest_report and latest_report.get("name"):
            return str(latest_report["name"])
        if selection_result:
            stock = selection_result.get("stock", {})
            if isinstance(stock, dict) and stock.get("name"):
                return str(stock["name"])
        try:
            return self.market_repository.get_security_name(symbol) or symbol
        except LocalMarketDataUnavailable:
            return symbol


def normalize_market_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "." in normalized:
        code, market = normalized.split(".", 1)
        return f"{code}.{market}"
    if normalized.startswith(("SZ", "SH", "BJ")):
        return f"{normalized[2:]}.{normalized[:2]}"
    if normalized.startswith(("6", "9")):
        return f"{normalized}.SH"
    if normalized.startswith(("4", "8")):
        return f"{normalized}.BJ"
    return f"{normalized}.SZ"
