import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.enums import WorkflowType
from app.local_data.repository import LocalMarketRepository
from app.main import create_app


@pytest.fixture
def isolated_workflow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "workflows.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "mock")
    get_settings.cache_clear()
    yield db_path
    get_settings.cache_clear()


@pytest.fixture
def isolated_workflow_and_data_db(tmp_path, monkeypatch):
    workflow_db = tmp_path / "workflows.db"
    data_db = tmp_path / "market.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(data_db))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "mock")
    get_settings.cache_clear()
    yield workflow_db, data_db
    get_settings.cache_clear()


def _bar(trade_date: str, close: float) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "open": close - 0.2,
        "high": close + 0.3,
        "low": close - 0.4,
        "close": close,
        "amount": 123.0,
        "volume": 456,
    }


def test_latest_selection_run_api_returns_empty_snapshot_without_runs(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/workflows/selection/runs/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "workflow": WorkflowType.SELECTION.value,
        "results": [],
        "run": None,
    }


def test_latest_selection_run_api_returns_persisted_snapshot_after_run(isolated_workflow_db):
    client = TestClient(create_app())

    run_response = client.post("/api/v1/workflows/selection/run")
    response = client.get("/api/v1/workflows/selection/runs/latest")

    assert run_response.status_code == 200
    assert response.status_code == 200
    run_payload = run_response.json()
    payload = response.json()
    assert payload["workflow"] == WorkflowType.SELECTION.value
    assert payload["results"] == run_payload["results"]
    assert payload["results"]
    assert "strategy_snapshot" in payload["results"][0]
    assert payload["run"]["workflow_type"] == WorkflowType.SELECTION.value
    assert payload["run"]["status"] == "success"
    assert payload["run"]["output_summary"] == f"results={len(payload['results'])}"


def _legacy_daily_review_api_uses_persisted_selection_snapshot_and_operations(isolated_workflow_db):
    first_client = TestClient(create_app())
    selection_response = first_client.post("/api/v1/workflows/selection/run")
    selected = next(
        result
        for result in selection_response.json()["results"]
        if result["action"] == "买入"
    )
    first_client.put(
        "/api/v1/review/operations",
        json={
            "operation_date": "2026-05-12",
            "operations": [
                {
                    "symbol": selected["stock"]["symbol"],
                    "name": selected["stock"]["name"],
                    "source": "selection",
                    "system_conclusion": selected["action"],
                    "user_action": "未买入",
                    "reason": "开盘波动偏大，等待确认",
                    "result_summary": "符合知行趋势线选股",
                }
            ],
        },
    )

    second_client = TestClient(create_app())
    response = second_client.post("/api/v1/workflows/daily-review/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.DAILY_REVIEW.value
    case = next(item for item in payload["cases"] if item["symbol"] == selected["stock"]["symbol"])
    assert case["user_action"] == "未买入"
    assert case["deviation"] == "该买未买"
    assert case["key_reason"] == "开盘波动偏大，等待确认"
    assert payload["deposition_candidates"]


def test_daily_review_api_uses_persisted_selection_snapshot_and_operations(isolated_workflow_db):
    first_client = TestClient(create_app())
    first_client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": "2026-05-24",
            "user_action": "observe",
            "review_conclusion": "manual stock review",
            "key_reason": "workspace level review",
        },
    )

    second_client = TestClient(create_app())
    response = second_client.post("/api/v1/workflows/daily-review/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.DAILY_REVIEW.value
    assert payload["cases"]
    assert payload["cases"][0]["symbol"] == "000001.SZ"
    assert payload["cases"][0]["review_conclusion"] == "manual stock review"
    assert payload["deposition_candidates"] == []


def test_run_holding_api_uses_manual_positions_and_local_market_data(
    isolated_workflow_and_data_db,
):
    _, data_db = isolated_workflow_and_data_db
    market_repository = LocalMarketRepository(data_db)
    market_repository.upsert_daily_bars(
        "000001.SZ",
        [
            _bar("2026-05-07", close=12.5),
            _bar("2026-05-08", close=13.8),
        ],
    )
    market_repository.upsert_security_metadata(
        [{"symbol": "000001.SZ", "name": "Ping An Bank", "market": "SZ"}]
    )
    client = TestClient(create_app())
    save_response = client.put(
        "/api/v1/portfolio/positions",
        json={
            "positions": [
                {
                    "symbol": "sz000001",
                    "quantity": 100,
                    "cost_price": 12.34,
                    "holding_days": 5,
                }
            ]
        },
    )

    response = client.post("/api/v1/workflows/holding/run")

    assert save_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.HOLDING.value
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["position"]["symbol"] == "000001.SZ"
    assert result["position"]["name"] == "Ping An Bank"
    assert result["position"]["current_price"] == 13.8
    assert result["stock"]["symbol"] == "000001.SZ"
    assert result["stock"]["name"] == "Ping An Bank"
    assert "2026-05-08" in result["stock"]["market_summary"]
    assert "13.8" in result["stock"]["market_summary"]
    assert "300750" not in {item["position"]["symbol"] for item in payload["results"]}


def test_run_selection_api_returns_empty_without_local_market_data(tmp_path, monkeypatch):
    workflow_db = tmp_path / "workflows.db"
    data_db = tmp_path / "missing-market.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(data_db))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "local")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post("/api/v1/workflows/selection/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.SELECTION.value
    assert payload["results"] == []
    get_settings.cache_clear()


def test_run_holding_api_returns_empty_without_manual_positions(isolated_workflow_and_data_db):
    client = TestClient(create_app())

    response = client.post("/api/v1/workflows/holding/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.HOLDING.value
    assert payload["results"] == []


def test_holding_results_persist_across_app_instances(isolated_workflow_db):
    first_client = TestClient(create_app())
    holding_response = first_client.post("/api/v1/workflows/holding/run")

    second_client = TestClient(create_app())
    dashboard_response = second_client.get("/api/v1/dashboard")

    assert holding_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["holding_results"] == holding_response.json()["results"]


def test_run_selection_api_returns_results():
    client = TestClient(create_app())

    response = client.post("/api/v1/workflows/selection/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == "选股"
    assert payload["results"]


def test_dashboard_api_returns_empty_state_without_real_inputs(
    isolated_workflow_and_data_db,
    monkeypatch,
):
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "local")
    get_settings.cache_clear()
    client = TestClient(create_app())
    client.post("/api/v1/workflows/selection/run")
    client.post("/api/v1/workflows/holding/run")
    client.post("/api/v1/workflows/daily-review/run")

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_results"] == []
    assert payload["holding_results"] == []
    assert payload["deposition_candidates"] == []
    get_settings.cache_clear()


def test_create_app_instances_do_not_share_in_memory_workflow_state(isolated_workflow_db):
    first_client = TestClient(create_app())
    second_client = TestClient(create_app())
    first_client.post("/api/v1/workflows/selection/run")

    response = second_client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_results"] == []
    assert payload["holding_results"] == []
    assert payload["deposition_candidates"] == []


def test_dashboard_api_returns_workflow_runs():
    client = TestClient(create_app())
    client.post("/api/v1/workflows/selection/run")
    client.post("/api/v1/workflows/holding/run")
    client.post("/api/v1/workflows/daily-review/run")

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    run_types = [run["workflow_type"] for run in payload["runs"]]
    assert len(run_types) == 3
    assert run_types == [
        WorkflowType.SELECTION.value,
        WorkflowType.HOLDING.value,
        WorkflowType.DAILY_REVIEW.value,
    ]


def test_weekly_review_aggregates_persisted_review_cases(isolated_workflow_db):
    client = TestClient(create_app())
    client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": "2026-05-24",
            "user_action": "observe",
            "review_conclusion": "manual stock review",
            "key_reason": "weekly summary seed",
            "worth_depositing": True,
        },
    )

    response = client.post("/api/v1/workflows/weekly-review/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == WorkflowType.WEEKLY_REVIEW.value
    assert payload["summary"]["case_count"] > 0
    assert payload["summary"]["depositable_count"] >= 0
    assert payload["summary"]["deviation_counts"]
    assert payload["summary"]["key_cases"]
    assert payload["summaries"]
