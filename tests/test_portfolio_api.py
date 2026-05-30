import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def isolated_workflow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "workflows.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(db_path))
    get_settings.cache_clear()
    yield db_path
    get_settings.cache_clear()


def test_positions_api_returns_empty_list_without_saved_positions(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/portfolio/positions")

    assert response.status_code == 200
    assert response.json() == {"positions": []}


def test_positions_api_replaces_and_persists_positions(isolated_workflow_db):
    first_client = TestClient(create_app())

    response = first_client.put(
        "/api/v1/portfolio/positions",
        json={
            "positions": [
                {
                    "symbol": "sz000001",
                    "quantity": 100,
                    "cost_price": 12.34,
                    "holding_days": 5,
                },
                {
                    "symbol": "sh600000",
                    "quantity": 200,
                    "cost_price": 8.9,
                    "holding_days": 12,
                },
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "positions": [
            {
                "symbol": "SZ000001",
                "quantity": 100,
                "cost_price": 12.34,
                "holding_days": 5,
            },
            {
                "symbol": "SH600000",
                "quantity": 200,
                "cost_price": 8.9,
                "holding_days": 12,
            },
        ]
    }

    second_client = TestClient(create_app())
    saved_response = second_client.get("/api/v1/portfolio/positions")

    assert saved_response.status_code == 200
    assert saved_response.json() == response.json()

    replace_response = second_client.put(
        "/api/v1/portfolio/positions",
        json={
            "positions": [
                {
                    "symbol": "000333",
                    "quantity": 10,
                    "cost_price": 55.5,
                    "holding_days": 1,
                }
            ]
        },
    )

    assert replace_response.status_code == 200
    assert replace_response.json() == {
        "positions": [
            {
                "symbol": "000333",
                "quantity": 10,
                "cost_price": 55.5,
                "holding_days": 1,
            }
        ]
    }
    assert second_client.get("/api/v1/portfolio/positions").json() == replace_response.json()
