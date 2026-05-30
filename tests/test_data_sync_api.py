import struct
from datetime import datetime
from zoneinfo import ZoneInfo

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


def _tdx_record() -> bytes:
    return struct.pack("<IIIIIfII", 20260515, 100, 200, 50, 150, 123.0, 456, 0)


def test_data_sync_status_api_returns_unified_progress(tmp_path, monkeypatch):
    db_path = tmp_path / "alphaagents.db"
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/data-sync/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_tdx"
    assert "freshness" in payload
    assert [stage["stage"] for stage in payload["progress"]] == [
        "daily_bars",
        "tdx_metadata",
        "freshness_check",
    ]


def test_data_sync_run_api_syncs_daily_bars_and_tdx_metadata(tmp_path, monkeypatch):
    tdx_root = tmp_path / "new_tdx_mock"
    lday = tdx_root / "vipdoc" / "sz" / "lday"
    lday.mkdir(parents=True)
    (lday / "sz000001.day").write_bytes(_tdx_record())
    hq_cache = tdx_root / "T0002" / "hq_cache"
    hq_cache.mkdir(parents=True)
    (hq_cache / "tdxzs3.cfg").write_text(
        "银行|880471|2|1|1|T1001\n股份制银行|881388|12|1|1|X500102\n",
        encoding="gbk",
    )
    (hq_cache / "tdxhy.cfg").write_text(
        "0|000001|T1001|||X500102\n",
        encoding="gbk",
    )
    db_path = tmp_path / "alphaagents.db"
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_TDX_ROOT", str(tdx_root))
    monkeypatch.setattr(
        "app.local_data.data_sync._now_china",
        lambda: datetime.fromisoformat("2026-05-17T10:00:00").replace(
            tzinfo=ZoneInfo("Asia/Shanghai")
        ),
    )
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post("/api/v1/data-sync/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["market_status"]["latest_trade_date"] == "2026-05-15"
    assert payload["daily_bars"]["imported_files"] == 1
    assert payload["metadata"] == {"profiles": 0, "sectors": 2, "sector_members": 2}
    assert payload["progress"][0]["status"] == "completed"
    assert payload["progress"][1]["status"] == "completed"
    assert LocalMarketRepository(db_path).list_sector_members("880471.SH") == [
        "000001.SZ"
    ]


def test_data_sync_run_api_reports_action_when_tdx_root_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(tmp_path / "alphaagents.db"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post("/api/v1/data-sync/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "action_required"
    assert payload["progress"][0]["status"] == "action_required"
    assert "通达信终端" in payload["progress"][0]["action"]
    assert "ALPHAAGENTS_TDX_ROOT" in payload["progress"][0]["action"]


def test_data_sync_status_reports_local_tdx_metadata_ready(tmp_path, monkeypatch):
    tdx_root = tmp_path / "new_tdx_mock"
    tdx_root.mkdir()
    monkeypatch.setenv("ALPHAAGENTS_DATA_DB", str(tmp_path / "alphaagents.db"))
    monkeypatch.setenv("ALPHAAGENTS_TDX_ROOT", str(tdx_root))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/v1/data-sync/status")

    assert response.status_code == 200
    metadata_stage = response.json()["progress"][1]
    assert metadata_stage["stage"] == "tdx_metadata"
    assert metadata_stage["status"] == "ready"
    assert "通达信" in metadata_stage["message"]
