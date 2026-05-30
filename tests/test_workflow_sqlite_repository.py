from datetime import UTC, datetime

from app.core.config import get_settings
from app.domain.enums import HoldingAction, SelectionAction, WorkflowType
from app.domain.models import (
    ExpertJudgement,
    HoldingAnalysisResult,
    HoldingPosition,
    SelectionResult,
    StockContext,
    StrategyConditionSnapshot,
    StrategySnapshot,
    WorkflowRun,
)
from app.repositories.sqlite import SQLiteWorkflowRepository
from app.workflows.service import AlphaAgentsWorkflowService


def _selection_result(symbol: str) -> SelectionResult:
    snapshot = StrategySnapshot(
        strategy_name="test-strategy",
        latest_trade_date="2026-05-11",
        conditions={
            "trend": StrategyConditionSnapshot(
                label="趋势",
                passed=True,
                actual=12.3,
                expected="大于 10",
            )
        },
    )
    return SelectionResult(
        stock=StockContext(
            symbol=symbol,
            name="测试股票",
            board="测试板块",
            market_summary="测试行情",
            fundamental_summary="测试基本面",
            board_heat_summary="测试热度",
            strategy_snapshot=snapshot,
        ),
        matched_standards=["趋势"],
        match_reason="命中测试策略",
        expert_judgements=[
            ExpertJudgement(
                skill_name="测试专家",
                scenario="选股",
                conclusion="关注",
                reason="仅用于测试持久化",
            )
        ],
        action=SelectionAction.WATCH,
        core_reason="验证策略快照能进入 SQLite payload",
        strategy_snapshot=snapshot,
    )


def test_sqlite_repository_saves_and_reads_latest_selection_run(tmp_path):
    repository = SQLiteWorkflowRepository(tmp_path / "nested" / "workflows.db")
    first_run = WorkflowRun(
        id="run-1",
        workflow_type=WorkflowType.SELECTION,
        executed_at=datetime(2026, 5, 10, 9, 30, tzinfo=UTC),
        input_summary="first",
        output_summary="results=1",
        status="success",
    )
    latest_run = WorkflowRun(
        id="run-2",
        workflow_type=WorkflowType.SELECTION,
        executed_at=datetime(2026, 5, 11, 9, 30, tzinfo=UTC),
        input_summary="latest",
        output_summary="results=1",
        status="success",
    )
    first_payload = {
        "workflow": WorkflowType.SELECTION.value,
        "results": [_selection_result("000001").model_dump(mode="json")],
        "run": first_run.model_dump(mode="json"),
    }
    latest_payload = {
        "workflow": WorkflowType.SELECTION.value,
        "results": [_selection_result("000002").model_dump(mode="json")],
        "run": latest_run.model_dump(mode="json"),
    }

    repository.save_selection_run(first_run, first_payload)
    repository.save_selection_run(latest_run, latest_payload)

    saved = repository.get_latest_selection_run()

    assert saved == latest_payload
    assert saved["run"]["executed_at"] == "2026-05-11T09:30:00Z"
    assert saved["results"][0]["strategy_snapshot"]["strategy_name"] == "test-strategy"
    assert (tmp_path / "nested" / "workflows.db").exists()


def test_sqlite_repository_returns_none_without_selection_runs(tmp_path):
    repository = SQLiteWorkflowRepository(tmp_path / "workflows.db")

    assert repository.get_latest_selection_run() is None


def test_run_selection_persists_sqlite_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "workflows.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "mock")
    get_settings.cache_clear()

    service = AlphaAgentsWorkflowService()
    response = service.run_selection()

    saved = SQLiteWorkflowRepository(db_path).get_latest_selection_run()
    dashboard_run = service.dashboard()["runs"][-1]
    expected_results = [result.model_dump(mode="json") for result in response["results"]]
    assert saved is not None
    assert saved["workflow"] == WorkflowType.SELECTION.value
    assert saved["results"] == expected_results
    assert saved["run"]["id"] == dashboard_run.id
    assert saved["run"]["workflow_type"] == WorkflowType.SELECTION.value

    get_settings.cache_clear()


def test_sqlite_repository_saves_and_reads_latest_holding_results(tmp_path):
    repository = SQLiteWorkflowRepository(tmp_path / "workflows.db")
    result = HoldingAnalysisResult(
        position=HoldingPosition(
            symbol="600519.SH",
            name="贵州茅台",
            quantity=100,
            cost_price=1500.0,
            current_price=1600.0,
            holding_days=20,
        ),
        stock=StockContext(
            symbol="600519.SH",
            name="贵州茅台",
            board="白酒",
            market_summary="趋势稳定",
            fundamental_summary="示例",
            board_heat_summary="示例",
        ),
        expert_judgements=[],
        action=HoldingAction.HOLD,
        action_reason="趋势未破坏",
        next_day_reminder="关注量能",
        risks=["波动"],
    )

    saved = repository.save_holding_results([result])

    assert saved[0]["position"]["symbol"] == "600519.SH"
    assert repository.list_holding_results() == saved
