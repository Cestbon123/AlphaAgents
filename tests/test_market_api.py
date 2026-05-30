import struct

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.local_data.repository import LocalMarketRepository
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", "")
    monkeypatch.setenv("ALPHAAGENTS_TDX_ROOT", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _bar() -> dict:
    return {
        "trade_date": "2026-05-06",
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "amount": 123.0,
        "volume": 456,
    }


def _tdx_record() -> bytes:
    return struct.pack("<IIIIIfII", 20260515, 100, 200, 50, 150, 123.0, 456, 0)


def _dated_bar(index: int) -> dict:
    close = float(index)
    return {
        "trade_date": f"2026-05-{index:02d}",
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "amount": close * 100,
        "volume": index * 100,
    }


def test_daily_bars_api_returns_local_bars(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_security_metadata(
        [{"symbol": "300750.SZ", "name": "宁德时代", "market": "SZ"}]
    )
    repository.upsert_daily_bars("300750.SZ", [_bar()])
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=120")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "300750.SZ"
    assert payload["name"] == "宁德时代"
    assert payload["source"] == "local"
    assert payload["message"] == ""
    assert payload["bars"][0]["indicators"]["macd"] == {
        "dif": 0.0,
        "dea": 0.0,
        "macd": 0.0,
    }
    assert payload["bars"][0]["indicators"]["kdj"] == {"k": 50.0, "d": 50.0, "j": 50.0}
    assert payload["bars"][0]["indicators"]["vol"] == {
        "volume": 456,
        "ma5": None,
        "ma10": None,
    }


def test_market_status_api_returns_local_data_state(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_daily_bars("300750.SZ", [_bar()])
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["bar_count"] == 1
    assert payload["symbol_count"] == 1
    assert payload["latest_trade_date"] == "2026-05-06"


def test_market_sectors_and_stocks_api_return_local_sector_quotes(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_security_metadata(
        [{"symbol": "600001.SH", "name": "测试银行", "market": "SH"}]
    )
    repository.upsert_sector_metadata(
        [{"sector_code": "881155.SH", "sector_name": "银行", "sector_type": "行业"}]
    )
    repository.upsert_sector_members(
        [{"sector_code": "881155.SH", "symbol": "600001.SH"}]
    )
    repository.upsert_daily_bars(
        "600001.SH",
        [
            {**_bar(), "trade_date": "2026-05-05", "close": 10.0},
            {**_bar(), "trade_date": "2026-05-06", "close": 11.0},
        ],
    )
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    sectors_response = client.get("/api/v1/market/sectors?sector_type=行业")
    stocks_response = client.get("/api/v1/market/stocks?sector_code=881155.SH")

    assert sectors_response.status_code == 200
    assert sectors_response.json()["sectors"][0]["sector_name"] == "银行"
    assert sectors_response.json()["sectors"][0]["member_count"] == 1
    assert stocks_response.status_code == 200
    stock = stocks_response.json()["stocks"][0]
    assert stock["symbol"] == "600001.SH"
    assert stock["name"] == "测试银行"
    assert stock["price"] == 11.0
    assert stock["change_pct"] == 10.0


def test_market_sync_api_imports_configured_tdx_daily_data(tmp_path, monkeypatch):
    tdx_root = tmp_path / "new_tdx_mock"
    lday = tdx_root / "vipdoc" / "sz" / "lday"
    lday.mkdir(parents=True)
    (lday / "sz000001.day").write_bytes(_tdx_record())
    db_path = tmp_path / "alphaagents.db"
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_TDX_ROOT", str(tdx_root))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post("/api/v1/market/sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["imported_files"] == 1
    assert payload["imported_bars"] == 1
    assert payload["market_status"]["latest_trade_date"] == "2026-05-15"


def test_market_sync_api_requires_configured_tdx_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(tmp_path / "alphaagents.db"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post("/api/v1/market/sync")

    assert response.status_code == 400
    assert "ALPHAAGENTS_TDX_ROOT" in response.json()["detail"]


def test_daily_bars_api_warms_indicators_with_extra_history(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    repository.upsert_daily_bars("300750.SZ", [_dated_bar(index) for index in range(1, 16)])
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=5")

    assert response.status_code == 200
    bars = response.json()["bars"]
    assert len(bars) == 5
    assert bars[0]["time"] == "2026-05-11"
    assert bars[0]["indicators"]["vol"]["ma10"] == 650.0




def test_daily_bars_api_returns_unavailable_when_db_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(tmp_path / "missing.db"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=120")

    assert response.status_code == 200
    assert response.json()["bars"] == []
    assert response.json()["source"] == "unavailable"
    assert "not found" in response.json()["message"]


@pytest.mark.parametrize(
    "db_name, db_content",
    [
        ("empty.db", b""),
        ("not-sqlite.db", b"not a sqlite database"),
    ],
)
def test_daily_bars_api_returns_unavailable_when_db_file_is_unreadable(
    tmp_path, monkeypatch, db_name, db_content
):
    db_path = tmp_path / db_name
    db_path.write_bytes(db_content)
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=120")

    assert response.status_code == 200
    assert response.json()["symbol"] == "300750.SZ"
    assert response.json()["bars"] == []
    assert response.json()["source"] == "unavailable"
    assert "unavailable" in response.json()["message"]


def test_daily_bars_api_returns_unavailable_when_market_table_is_missing(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    LocalMarketRepository(db_path)._connect().close()
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=120")

    assert response.status_code == 200
    assert response.json()["symbol"] == "300750.SZ"
    assert response.json()["bars"] == []
    assert response.json()["source"] == "unavailable"
    assert "market_daily" in response.json()["message"]


def test_daily_bars_api_returns_unavailable_when_market_table_schema_is_incompatible(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    with repository._connect() as connection:
        connection.execute(
            """
            CREATE TABLE market_daily (
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL
            )
            """
        )
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=000001.SZ&limit=120")

    assert response.status_code == 200
    assert response.json()["symbol"] == "000001.SZ"
    assert response.json()["bars"] == []
    assert response.json()["source"] == "unavailable"
    assert "unavailable" in response.json()["message"]


def test_daily_bars_api_returns_empty_local_result_when_symbol_is_missing(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/market/daily-bars?symbol=300750.SZ&limit=120")

    assert response.status_code == 200
    assert response.json()["bars"] == []
    assert response.json()["source"] == "local"
    assert "No local daily bars" in response.json()["message"]
