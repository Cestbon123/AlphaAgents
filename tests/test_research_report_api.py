import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.external_data.cache import ExternalDataCache
from app.local_data.repository import LocalMarketRepository
from app.main import create_app


@pytest.fixture
def isolated_research_dbs(tmp_path, monkeypatch):
    workflow_db = tmp_path / "workflows.db"
    data_db = tmp_path / "market.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(data_db))
    get_settings.cache_clear()
    yield workflow_db, data_db
    get_settings.cache_clear()


def _seed_daily_data(data_db):
    repository = LocalMarketRepository(data_db)
    repository.upsert_security_profiles(
        [
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "market": "SZ",
                "market_category": "主板",
                "is_st": False,
            }
        ]
    )
    repository.upsert_daily_bars(
        "000001.SZ",
        [
            {
                "trade_date": f"2026-05-{day:02d}",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.0 + day * 0.03,
                "amount": 1000.0,
                "volume": 100,
            }
            for day in range(1, 23)
        ],
    )


def _seed_external_cache(workflow_db):
    cache = ExternalDataCache(workflow_db)
    cache.set("000001.SZ", "valuation", {"pe_ttm": 8.5, "pb": 0.8, "market_cap": 2100})
    cache.set("000001.SZ", "money_flow", {"trade_date": "2026-05-22", "main_net_inflow": 500})
    cache.set("000001.SZ", "dragon_tiger", [])
    cache.set("000001.SZ", "sectors", [{"sector_name": "银行", "sector_type": "行业"}])
    cache.set("000001.SZ", "announcements", [{"title": "年度报告"}])
    cache.set("000001.SZ", "news", [{"title": "经营稳健"}])


def test_research_report_api_generates_and_persists_report(isolated_research_dbs):
    workflow_db, data_db = isolated_research_dbs
    _seed_daily_data(data_db)
    _seed_external_cache(workflow_db)
    client = TestClient(create_app())

    response = client.post("/api/v1/reports/research/run", json={"symbol": "000001"})

    assert response.status_code == 200
    report = response.json()["report"]
    assert report["symbol"] == "000001.SZ"
    assert report["name"] == "平安银行"
    assert report["final_decision"] in {"重点跟踪", "观察", "暂不跟踪", "放弃"}
    assert len(report["analyst_reports"]) == 9
    assert "多专家研究报告" in report["report_text"]
    assert "交易指令" in report["report_text"]

    latest_response = TestClient(create_app()).get(
        "/api/v1/reports/research/latest?symbol=000001.SZ"
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["report"] == report


def test_research_report_api_succeeds_with_data_gaps(isolated_research_dbs):
    client = TestClient(create_app())

    response = client.post("/api/v1/reports/research/run", json={"symbol": "000001.SZ"})

    assert response.status_code == 200
    report = response.json()["report"]
    assert report["symbol"] == "000001.SZ"
    assert report["data_gaps"]
    assert "本地日线数据缺失" in "；".join(report["data_gaps"])
