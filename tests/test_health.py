import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setenv(
        "ALPHAAGENTS_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000,null",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AlphaAgents"}


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "null",
    ],
)
def test_default_cors_allows_local_static_workbench_origins(origin):
    client = TestClient(create_app())

    response = client.get("/api/v1/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
