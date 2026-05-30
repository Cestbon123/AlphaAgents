import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.main import create_app


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


def test_latest_daily_report_api_returns_null_without_report(isolated_workflow_and_data_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/reports/daily/latest")

    assert response.status_code == 200
    assert response.json() == {"report": None}


def test_daily_report_api_generates_and_persists_report(isolated_workflow_and_data_db):
    _, data_db = isolated_workflow_and_data_db
    market_repository = LocalMarketRepository(data_db)
    market_repository.upsert_daily_bars(
        "000001.SZ",
        [
            {
                "trade_date": "2026-05-08",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "amount": 1000.0,
                "volume": 100,
            }
        ],
    )
    first_client = TestClient(create_app())
    first_client.post("/api/v1/workflows/selection/run")
    first_client.put(
        "/api/v1/review/operations",
        json={
            "operation_date": "2026-05-12",
            "operations": [
                {
                    "symbol": "300750",
                    "name": "宁德时代",
                    "source": "selection",
                    "system_conclusion": "买入",
                    "user_action": "未买入",
                    "reason": "等待确认",
                    "result_summary": "符合知行趋势线选股",
                }
            ],
        },
    )
    first_client.post(
        "/api/v1/stocks/300750/reviews",
        json={
            "review_date": "2026-05-12",
            "user_action": "未买入",
            "review_conclusion": "错过机会",
            "key_reason": "等待确认导致未跟随",
            "deviation": "该买未买",
            "worth_depositing": True,
        },
    )
    first_client.post(
        "/api/v1/stocks/300750/depositions",
        json={
            "kind": "错误案例",
            "title": "趋势确认后的犹豫成本",
            "content": "复盘时从当前个股沉淀，而不是由每日复盘批量生成。",
        },
    )

    response = first_client.post(
        "/api/v1/reports/daily/run",
        json={"report_date": "2026-05-12"},
    )

    assert response.status_code == 200
    report = response.json()["report"]
    assert report["report_date"] == "2026-05-12"
    assert "latest_trade_date=2026-05-08" in report["market_summary"]
    assert "候选" in report["selection_summary"]
    assert "复盘案例" in report["review_summary"]
    assert "该买未买 1" in report["review_summary"]
    assert "沉淀候选" in report["deposition_summary"]
    assert "结构化日报" in report["report_text"]
    assert "交易指令" not in report["report_text"]

    second_client = TestClient(create_app())
    latest_response = second_client.get("/api/v1/reports/daily/latest")

    assert latest_response.status_code == 200
    assert latest_response.json()["report"] == report
