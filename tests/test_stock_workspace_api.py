import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.main import create_app


@pytest.fixture
def isolated_stock_workspace_dbs(tmp_path, monkeypatch):
    workflow_db = tmp_path / "workflows.db"
    data_db = tmp_path / "market.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(data_db))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "mock")
    monkeypatch.setenv("ALPHAAGENTS_LLM_API_KEY", "")
    monkeypatch.setenv("ALPHAAGENTS_EXTERNAL_DATA_LIVE_ENABLED", "false")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()
    yield workflow_db, data_db
    get_settings.cache_clear()


def _seed_market(data_db):
    repository = LocalMarketRepository(data_db)
    repository.upsert_security_metadata(
        [{"symbol": "000001.SZ", "name": "平安银行", "market": "SZ"}]
    )
    repository.upsert_daily_bars(
        "000001.SZ",
        [
            {
                "trade_date": "2026-05-21",
                "open": 10.0,
                "high": 10.8,
                "low": 9.8,
                "close": 10.4,
                "amount": 1000.0,
                "volume": 100,
            },
            {
                "trade_date": "2026-05-22",
                "open": 10.4,
                "high": 10.9,
                "low": 10.1,
                "close": 10.7,
                "amount": 1200.0,
                "volume": 120,
            },
        ],
    )


def test_stock_workspace_returns_empty_usable_state(isolated_stock_workspace_dbs):
    client = TestClient(create_app())

    response = client.get("/api/v1/stocks/000001/workspace")

    assert response.status_code == 200
    workspace = response.json()["workspace"]
    assert workspace["symbol"] == "000001.SZ"
    assert workspace["tracking_state"]["status"] == "观察"
    assert workspace["operation_records"] == []
    assert workspace["review_cases"] == []
    assert workspace["deposition_candidates"] == []
    assert workspace["data_gaps"]


def test_stock_workspace_aggregates_stock_actions_and_research(
    isolated_stock_workspace_dbs,
):
    _, data_db = isolated_stock_workspace_dbs
    _seed_market(data_db)
    client = TestClient(create_app())

    research_response = client.post("/api/v1/stocks/000001/research/run")
    operation_response = client.post(
        "/api/v1/stocks/000001/operations",
        json={
            "operation_date": "2026-05-24",
            "user_action": "观察",
            "reason": "等待放量确认",
        },
    )
    review_response = client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": "2026-05-24",
            "user_action": "观察",
            "review_conclusion": "信号有效但未确认",
            "key_reason": "量能不足，继续跟踪",
            "worth_depositing": True,
        },
    )
    review_case_id = review_response.json()["review_case"]["id"]
    deposition_response = client.post(
        "/api/v1/stocks/000001/depositions",
        json={
            "kind": "风险提醒",
            "title": "放量确认前不提高跟踪级别",
            "content": "技术形态成立但量能不足时只观察。",
            "review_case_id": review_case_id,
        },
    )
    tracking_response = client.patch(
        "/api/v1/stocks/000001/tracking",
        json={"status": "重点跟踪", "note": "等待二次确认"},
    )
    workspace_response = client.get("/api/v1/stocks/000001/workspace")

    assert research_response.status_code == 200
    assert operation_response.status_code == 200
    assert review_response.status_code == 200
    assert deposition_response.status_code == 200
    assert tracking_response.status_code == 200
    workspace = workspace_response.json()["workspace"]
    assert workspace["symbol"] == "000001.SZ"
    assert workspace["name"] == "平安银行"
    assert workspace["latest_bar"]["close"] == 10.7
    assert workspace["latest_research_report"]["symbol"] == "000001.SZ"
    assert workspace["operation_records"][0]["reason"] == "等待放量确认"
    assert workspace["review_cases"][0]["id"] == review_case_id
    assert workspace["deposition_candidates"][0]["review_case_id"] == review_case_id
    assert workspace["tracking_state"]["status"] == "重点跟踪"


def test_daily_review_summarizes_user_written_stock_reviews(
    isolated_stock_workspace_dbs,
):
    client = TestClient(create_app())
    client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": "2026-05-24",
            "user_action": "观察",
            "review_conclusion": "用户主动复盘",
            "key_reason": "围绕个股沉淀",
        },
    )

    response = client.post("/api/v1/workflows/daily-review/run")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["symbol"] == "000001.SZ"
    assert payload["deposition_candidates"] == []


def test_case_library_lists_review_cases_and_depositions_by_symbol(
    isolated_stock_workspace_dbs,
):
    client = TestClient(create_app())
    review_response = client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": "2026-05-24",
            "user_action": "观察",
            "review_conclusion": "信号有效但未确认",
            "key_reason": "围绕个股工作台写复盘",
            "worth_depositing": True,
        },
    )
    review_case_id = review_response.json()["review_case"]["id"]
    client.post(
        "/api/v1/stocks/000001/depositions",
        json={
            "kind": "风险提醒",
            "title": "等待放量确认",
            "content": "沉淀必须绑定股票和复盘来源。",
            "review_case_id": review_case_id,
        },
    )

    response = client.get("/api/v1/stocks/cases/list?symbol=000001.SZ")

    assert response.status_code == 200
    cases = response.json()["cases"]
    assert {item["item_type"] for item in cases} == {
        "review_case",
        "deposition_candidate",
    }
    assert {item["symbol"] for item in cases} == {"000001.SZ"}
    assert any(item["review_case_id"] == review_case_id for item in cases)


def test_research_report_list_returns_generated_reports_only(
    isolated_stock_workspace_dbs,
):
    _, data_db = isolated_stock_workspace_dbs
    _seed_market(data_db)
    client = TestClient(create_app())

    run_response = client.post("/api/v1/stocks/000001/research/run")
    list_response = client.get("/api/v1/reports/research")

    assert run_response.status_code == 200
    assert list_response.status_code == 200
    reports = list_response.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["symbol"] == "000001.SZ"
    assert reports[0]["generation_mode"] in {
        "deterministic_fallback",
        "llm_tradingagents_style",
    }
    assert "analyst_reports" in reports[0]
