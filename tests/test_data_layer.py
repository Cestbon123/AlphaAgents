from app.adapters.broker import MockBrokerDataProvider
from app.domain.enums import HoldingAction, SelectionAction, WorkflowType
from app.domain.models import (
    ExpertJudgement,
    HoldingAnalysisResult,
    HoldingPosition,
    SelectionResult,
    StockContext,
    WorkflowRun,
)
from app.repositories.memory import InMemoryAlphaAgentsRepository


def _stock_context() -> StockContext:
    return StockContext(
        symbol="000001",
        name="Ping An Bank",
        board="Banking",
        market_summary="Range-bound",
        fundamental_summary="Stable fundamentals",
        board_heat_summary="Low board heat",
        strategy_hits=["Pullback"],
        profile_summary="Low-volatility sample",
    )


def _expert_judgement() -> ExpertJudgement:
    return ExpertJudgement(
        skill_name="trend",
        scenario="pullback",
        conclusion="watch",
        reason="price is near moving average",
    )


def _selection_result() -> SelectionResult:
    return SelectionResult(
        stock=_stock_context(),
        matched_standards=["trend pullback"],
        match_reason="candidate matches pullback setup",
        expert_judgements=[_expert_judgement()],
        action=SelectionAction.WATCH,
        core_reason="observe confirmation",
    )


def _holding_result() -> HoldingAnalysisResult:
    return HoldingAnalysisResult(
        position=HoldingPosition(
            symbol="000001",
            name="Ping An Bank",
            quantity=100,
            cost_price=10.0,
            current_price=10.5,
            holding_days=3,
        ),
        stock=_stock_context(),
        expert_judgements=[_expert_judgement()],
        action=HoldingAction.HOLD,
        action_reason="trend remains intact",
        next_day_reminder="watch volume",
    )


def test_mock_broker_returns_stock_contexts():
    provider = MockBrokerDataProvider()

    contexts = provider.get_stock_contexts(["000001"])

    assert len(contexts) == 1
    assert contexts[0].symbol == "000001"
    assert contexts[0].strategy_hits


def test_memory_repository_saves_workflow_runs():
    repository = InMemoryAlphaAgentsRepository()
    run = WorkflowRun(
        id="run-1",
        workflow_type=WorkflowType.SELECTION,
        executed_at="2026-04-24T18:00:00",
        input_summary="输入 1 只候选股",
        output_summary="输出 1 条买入建议",
        status="success",
    )

    repository.save_run(run)

    assert repository.list_runs()[0].id == "run-1"


def test_memory_repository_copies_selection_result_batches():
    repository = InMemoryAlphaAgentsRepository()
    results = [_selection_result()]

    repository.save_selection_results(results)
    results.clear()

    assert len(repository.list_selection_results()) == 1


def test_memory_repository_copies_holding_result_batches():
    repository = InMemoryAlphaAgentsRepository()
    results = [_holding_result()]

    repository.save_holding_results(results)
    results.clear()

    assert len(repository.list_holding_results()) == 1
