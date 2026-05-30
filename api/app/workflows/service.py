from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from app.adapters.broker import MockBrokerDataProvider
from app.core.config import get_settings
from app.domain.enums import WorkflowType
from app.domain.models import (
    HoldingPosition,
    OperationRecord,
    SelectionResult,
    StockContext,
    WorkflowRun,
)
from app.expert_skills.registry import ExpertSkillRegistry
from app.external_data.astock import ExternalResearchDataProvider
from app.external_data.cache import ExternalDataCache
from app.llm.client import OpenAICompatibleClient
from app.local_data.repository import (
    LocalMarketDataUnavailable,
    LocalMarketRepository,
)
from app.repositories.memory import InMemoryAlphaAgentsRepository
from app.repositories.sqlite import SQLiteWorkflowRepository
from app.strategies.basic import BasicSelectionStrategy
from app.strategies.config import ZHIXING_STRATEGY_ID, merge_strategy_config
from app.strategies.zhixing import ZhixingStrategyParams, ZhixingTrendSelectionStrategy
from app.workflows.daily_report import DailyReportWorkflow
from app.workflows.holding import HoldingWorkflow
from app.workflows.research import ResearchWorkflow
from app.workflows.research_context import ResearchContextBuilder
from app.workflows.review import ReviewWorkflow
from app.workflows.selection import SelectionWorkflow


class AlphaAgentsWorkflowService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.data_provider = MockBrokerDataProvider()
        self.repository = InMemoryAlphaAgentsRepository()
        self.workflow_repository = SQLiteWorkflowRepository(self.settings.workflow_db)
        self.skills = ExpertSkillRegistry.default()

    def run_selection(self) -> dict[str, object]:
        strategy = self._selection_strategy()
        results = SelectionWorkflow(
            strategy=strategy,
            skills=self.skills,
            repository=self.repository,
        ).run()
        run = self._record_run(
            workflow_type=WorkflowType.SELECTION,
            input_summary=self._selection_input_summary(),
            output_summary=f"results={len(results)}",
        )
        self.workflow_repository.save_selection_run(
            run=run,
            payload={
                "workflow": WorkflowType.SELECTION.value,
                "results": [result.model_dump(mode="json") for result in results],
                "run": run.model_dump(mode="json"),
            },
        )
        return {"workflow": WorkflowType.SELECTION.value, "results": results}

    def get_latest_selection_run(self) -> dict[str, object]:
        payload = self.workflow_repository.get_latest_selection_run()
        if payload is None:
            return {
                "workflow": WorkflowType.SELECTION.value,
                "results": [],
                "run": None,
            }
        return payload

    def run_daily_report(self, report_date: date | None = None) -> dict[str, object]:
        target_date = report_date or datetime.now(UTC).date()
        review_cases = self.workflow_repository.list_review_cases(target_date)
        if not review_cases:
            review_cases = self.workflow_repository.get_latest_review_cases()
        report = DailyReportWorkflow(
            market_repository=LocalMarketRepository(self.settings.data_db),
            latest_selection_run=self.workflow_repository.get_latest_selection_run(),
            holding_results=(
                self.workflow_repository.list_holding_results()
                or self.repository.list_holding_results()
            ),
            operation_records=self.workflow_repository.list_operation_records(),
            review_cases=review_cases,
            deposition_candidates=self.workflow_repository.list_deposition_candidates(),
        ).generate(target_date)
        saved_report = self.workflow_repository.save_daily_report(report)
        return {"report": saved_report}

    def get_latest_daily_report(self) -> dict[str, object | None]:
        return {"report": self.workflow_repository.get_latest_daily_report()}

    def run_research_report(self, symbol: str) -> dict[str, object]:
        normalized_symbol = _normalize_market_symbol(symbol)
        context = ResearchContextBuilder(
            market_repository=LocalMarketRepository(self.settings.data_db),
            external_provider=ExternalResearchDataProvider(
                cache=ExternalDataCache(self.settings.workflow_db),
                live_enabled=self.settings.external_data_live_enabled,
            ),
        ).build(normalized_symbol)
        report = ResearchWorkflow(
            llm_client=OpenAICompatibleClient(
                api_key=self.settings.resolved_llm_api_key,
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model,
                timeout_seconds=self.settings.llm_timeout_seconds,
            )
        ).run(context)
        saved_report = self.workflow_repository.save_research_report(report)
        self._record_run(
            workflow_type=WorkflowType.RESEARCH_REPORT,
            input_summary=f"stock research symbol={normalized_symbol}",
            output_summary=f"decision={saved_report['final_decision']}",
        )
        return {"report": saved_report}

    def get_latest_research_report(self, symbol: str | None = None) -> dict[str, object | None]:
        normalized_symbol = _normalize_market_symbol(symbol) if symbol else None
        return {"report": self.workflow_repository.get_latest_research_report(normalized_symbol)}

    def run_holding(self) -> dict[str, object]:
        manual_positions = self.workflow_repository.list_positions()
        positions: list[HoldingPosition] | None = []
        contexts: list[StockContext] | None = []
        input_summary = "manual portfolio positions=0"
        if manual_positions:
            positions, contexts = self._manual_holding_inputs(manual_positions)
            input_summary = f"manual portfolio positions={len(positions)}"

        results = HoldingWorkflow(
            data_provider=self.data_provider,
            skills=self.skills,
            repository=self.repository,
            positions=positions,
            contexts=contexts,
        ).run()
        persisted_results = self.workflow_repository.save_holding_results(results)
        self._record_run(
            workflow_type=WorkflowType.HOLDING,
            input_summary=input_summary,
            output_summary=f"results={len(results)}",
        )
        return {"workflow": WorkflowType.HOLDING.value, "results": persisted_results}

    def run_daily_review(self) -> dict[str, object]:
        review_date = datetime.now(UTC).date()
        persisted_cases = self.workflow_repository.list_review_cases(review_date)
        if not persisted_cases:
            persisted_cases = self.workflow_repository.list_review_cases()
        persisted_candidates = []
        self._record_run(
            workflow_type=WorkflowType.DAILY_REVIEW,
            input_summary=f"stock_review_cases={len(persisted_cases)}",
            output_summary=(
                f"cases={len(persisted_cases)}, "
                f"deposition_candidates={len(persisted_candidates)}"
            ),
        )
        return {
            "workflow": WorkflowType.DAILY_REVIEW.value,
            "cases": persisted_cases,
            "deposition_candidates": persisted_candidates,
        }

    def run_weekly_review(self) -> dict[str, object]:
        persisted_cases = self.workflow_repository.list_review_cases()
        review_workflow = ReviewWorkflow(self.repository)
        summary = review_workflow.summarize_weekly_cases(persisted_cases)
        summaries = review_workflow.weekly_summary_lines(summary)
        self._record_run(
            workflow_type=WorkflowType.WEEKLY_REVIEW,
            input_summary=f"review_cases={len(persisted_cases)}",
            output_summary=f"summaries={len(summaries)}",
        )
        return {
            "workflow": WorkflowType.WEEKLY_REVIEW.value,
            "summary": summary,
            "summaries": summaries,
        }

    def dashboard(self) -> dict[str, object]:
        persisted_deposition_candidates = self.workflow_repository.list_deposition_candidates()
        return {
            "selection_results": self.repository.list_selection_results(),
            "holding_results": (
                self.workflow_repository.list_holding_results()
                or self.repository.list_holding_results()
            ),
            "review_cases": self.workflow_repository.get_latest_review_cases(),
            "deposition_candidates": (
                persisted_deposition_candidates
                or self.repository.list_deposition_candidates()
            ),
            "runs": self.repository.list_runs(),
        }

    def _record_run(
        self,
        workflow_type: WorkflowType,
        input_summary: str,
        output_summary: str,
    ) -> WorkflowRun:
        run = WorkflowRun(
            id=str(uuid4()),
            workflow_type=workflow_type,
            executed_at=datetime.now(UTC),
            input_summary=input_summary,
            output_summary=output_summary,
            status="success",
        )
        self.repository.save_run(run)
        return run

    def _selection_strategy(
        self,
    ) -> BasicSelectionStrategy | ZhixingTrendSelectionStrategy | EmptySelectionStrategy:
        data_source = self.settings.selection_data_source.lower()
        if data_source == "local":
            repository = LocalMarketRepository(self.settings.data_db)
            if not repository.status()["available"]:
                return EmptySelectionStrategy()
            strategy_config = merge_strategy_config(
                self.workflow_repository.get_strategy_config(ZHIXING_STRATEGY_ID)
            )
            if not strategy_config["enabled"]:
                return EmptySelectionStrategy()
            return ZhixingTrendSelectionStrategy(
                repository=repository,
                stock_pool=self.settings.resolved_selection_stock_pool,
                params=ZhixingStrategyParams.from_mapping(strategy_config["params"]),
            )
        if data_source == "mock":
            return BasicSelectionStrategy(self.data_provider)
        return EmptySelectionStrategy()

    def _selection_input_summary(self) -> str:
        if self.settings.selection_data_source.lower() == "local":
            return (
                "local tdx daily zhixing selection, "
                f"stock_pool={len(self.settings.resolved_selection_stock_pool) or 'all'}"
            )
        if self.settings.selection_data_source.lower() == "mock":
            return "mock broker selection candidates"
        return f"{self.settings.selection_data_source} selection source unavailable"

    def _review_selection_results(self) -> list[SelectionResult]:
        in_memory_results = self.repository.list_selection_results()
        if in_memory_results:
            return in_memory_results

        payload = self.workflow_repository.get_latest_selection_run()
        if not payload:
            return []

        return [
            SelectionResult.model_validate(result)
            for result in payload.get("results", [])
        ]

    def _operation_records(self) -> list[OperationRecord]:
        return [
            OperationRecord.model_validate(record)
            for record in self.workflow_repository.list_operation_records()
        ]

    def _manual_holding_inputs(
        self, raw_positions: list[dict[str, object]]
    ) -> tuple[list[HoldingPosition], list[StockContext]]:
        market_repository = LocalMarketRepository(self.settings.data_db)
        positions: list[HoldingPosition] = []
        contexts: list[StockContext] = []

        for raw_position in raw_positions:
            symbol = _normalize_market_symbol(str(raw_position["symbol"]))
            bars = self._daily_bars(market_repository, symbol)
            latest_bar = bars[-1] if bars else None
            close = float(latest_bar["close"]) if latest_bar else float(raw_position["cost_price"])
            name = self._security_name(market_repository, symbol) or symbol
            position = HoldingPosition(
                symbol=symbol,
                name=name,
                quantity=int(raw_position["quantity"]),
                cost_price=float(raw_position["cost_price"]),
                current_price=close,
                holding_days=int(raw_position["holding_days"]),
            )
            positions.append(position)
            contexts.append(_holding_stock_context(position, bars))

        return positions, contexts

    def _daily_bars(
        self, market_repository: LocalMarketRepository, symbol: str
    ) -> list[dict[str, object]]:
        try:
            return market_repository.get_daily_bars(symbol, limit=2)
        except LocalMarketDataUnavailable:
            return []

    def _security_name(self, market_repository: LocalMarketRepository, symbol: str) -> str | None:
        try:
            return market_repository.get_security_name(symbol)
        except LocalMarketDataUnavailable:
            return None


class EmptySelectionStrategy:
    def select_candidates(self) -> list[StockContext]:
        return []


def _normalize_market_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "." in normalized:
        code, market = normalized.split(".", 1)
        return f"{code}.{market}"
    if normalized.startswith(("SZ", "SH")):
        return f"{normalized[2:]}.{normalized[:2]}"
    if normalized.startswith(("BJ",)):
        return f"{normalized[2:]}.{normalized[:2]}"
    if normalized.startswith(("6", "9")):
        return f"{normalized}.SH"
    if normalized.startswith(("4", "8")):
        return f"{normalized}.BJ"
    return f"{normalized}.SZ"


def _holding_stock_context(
    position: HoldingPosition, bars: list[dict[str, object]]
) -> StockContext:
    return StockContext(
        symbol=position.symbol,
        name=position.name,
        board="manual portfolio",
        market_summary=_market_summary(bars, position.current_price),
        fundamental_summary="Manual position; fundamentals are not evaluated yet.",
        board_heat_summary="Local board heat is not evaluated yet.",
        strategy_hits=["manual_position"],
        profile_summary="User-maintained holding for research review.",
    )


def _market_summary(bars: list[dict[str, object]], current_price: float) -> str:
    if not bars:
        return f"latest_trade_date=unknown; close={current_price}"

    latest = bars[-1]
    summary = f"latest_trade_date={latest['time']}; close={latest['close']}"
    if len(bars) < 2:
        return summary

    previous_close = float(bars[-2]["close"])
    if previous_close == 0:
        return summary

    change_pct = (float(latest["close"]) - previous_close) / previous_close * 100
    return f"{summary}; change_pct={change_pct:.2f}%"
