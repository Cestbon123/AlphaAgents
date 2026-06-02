from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from app.domain.models import DailyReport, HoldingAnalysisResult
from app.local_data.repository import LocalMarketRepository


class DailyReportWorkflow:
    def __init__(
        self,
        *,
        market_repository: LocalMarketRepository,
        latest_selection_run: dict[str, object] | None,
        holding_results: list[HoldingAnalysisResult],
        operation_records: list[dict[str, object]],
        review_cases: list[dict[str, object]],
        deposition_candidates: list[dict[str, object]],
    ) -> None:
        self._market_repository = market_repository
        self._latest_selection_run = latest_selection_run
        self._holding_results = holding_results
        self._operation_records = operation_records
        self._review_cases = review_cases
        self._deposition_candidates = deposition_candidates

    def generate(self, report_date: date) -> DailyReport:
        market_summary = self._market_summary()
        selection_summary = self._selection_summary()
        holding_summary = self._holding_summary()
        review_summary = self._review_summary(report_date)
        deposition_summary = self._deposition_summary()
        report_text = "\n".join(
            [
                f"# AlphaAgents 结构化日报 {report_date.isoformat()}",
                "",
                f"市场摘要：{market_summary}",
                f"选股摘要：{selection_summary}",
                f"持股摘要：{holding_summary}",
                f"复盘摘要：{review_summary}",
                f"沉淀摘要：{deposition_summary}",
                "",
                "说明：本报告仅用于投研、复盘、分析和决策辅助，仅作研究留痕。",
            ]
        )
        return DailyReport(
            report_date=report_date,
            market_summary=market_summary,
            selection_summary=selection_summary,
            holding_summary=holding_summary,
            review_summary=review_summary,
            deposition_summary=deposition_summary,
            report_text=report_text,
        )

    def _market_summary(self) -> str:
        status = self._market_repository.status()
        if not status.get("available"):
            return f"本地行情不可用：{status.get('message', 'unknown')}"
        return (
            f"本地行情可用，latest_trade_date={status.get('latest_trade_date')}，"
            f"symbol_count={status.get('symbol_count')}，bar_count={status.get('bar_count')}"
        )

    def _selection_summary(self) -> str:
        results = _as_list((self._latest_selection_run or {}).get("results"))
        if not results:
            return "暂无选股结果快照。"
        counts = Counter(str(result.get("action", "")) for result in results)
        return (
            f"候选 {len(results)} 只，"
            f"买入 {counts.get('买入', 0)}，"
            f"待观察 {counts.get('待观察', 0)}，"
            f"放弃 {counts.get('放弃', 0)}。"
        )

    def _holding_summary(self) -> str:
        if not self._holding_results:
            return "暂无持股分析结果。"
        counts = Counter(_holding_action(result) for result in self._holding_results)
        details = "，".join(f"{action} {count}" for action, count in counts.items())
        return f"持股分析 {len(self._holding_results)} 条，{details}。"

    def _review_summary(self, report_date: date) -> str:
        dated_cases = [
            review_case
            for review_case in self._review_cases
            if str(review_case.get("review_date")) == report_date.isoformat()
        ]
        cases = dated_cases or self._review_cases
        if cases:
            deviations = Counter(str(review_case.get("deviation", "")) for review_case in cases)
            details = "，".join(f"{deviation} {count}" for deviation, count in deviations.items())
            return f"复盘案例 {len(cases)} 条，{details}。"

        records = [
            record
            for record in self._operation_records
            if str(record.get("operation_date")) == report_date.isoformat()
        ]
        if not records:
            return "当日暂无实际操作记录。"
        actions = Counter(str(record.get("user_action", "")) for record in records)
        details = "，".join(f"{action} {count}" for action, count in actions.items())
        return f"实际操作记录 {len(records)} 条，{details}。"

    def _deposition_summary(self) -> str:
        if not self._deposition_candidates:
            return "暂无沉淀候选。"
        counts = Counter(
            str(candidate.get("status", ""))
            for candidate in self._deposition_candidates
        )
        details = "，".join(f"{status} {count}" for status, count in counts.items())
        return f"沉淀候选 {len(self._deposition_candidates)} 条，{details}。"


def _as_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _holding_action(result: HoldingAnalysisResult | dict[str, Any]) -> str:
    if isinstance(result, dict):
        return str(result.get("action", ""))
    return result.action.value
