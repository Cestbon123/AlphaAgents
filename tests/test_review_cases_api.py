import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def isolated_workflow_db(tmp_path, monkeypatch):
    db_path = tmp_path / "workflows.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(db_path))
    monkeypatch.setenv("ALPHAAGENTS_SELECTION_DATA_SOURCE", "mock")
    get_settings.cache_clear()
    yield db_path
    get_settings.cache_clear()


def test_review_cases_latest_api_returns_empty_list_without_review(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/review/cases/latest")

    assert response.status_code == 200
    assert response.json() == {"cases": []}


def _create_stock_review(client: TestClient, review_date: str = "2026-05-24") -> dict[str, object]:
    response = client.post(
        "/api/v1/stocks/000001/reviews",
        json={
            "review_date": review_date,
            "user_action": "observe",
            "review_conclusion": "manual stock review",
            "key_reason": "workspace level review",
        },
    )
    assert response.status_code == 200
    return response.json()["review_case"]


def test_stock_review_persists_cases_and_dashboard_reads_them(isolated_workflow_db):
    first_client = TestClient(create_app())
    generated_cases = [_create_stock_review(first_client)]

    second_client = TestClient(create_app())
    latest_response = second_client.get("/api/v1/review/cases/latest")
    dashboard_response = second_client.get("/api/v1/dashboard")

    assert latest_response.status_code == 200
    assert latest_response.json()["cases"] == generated_cases
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["review_cases"] == generated_cases


def test_review_cases_api_filters_by_review_date(isolated_workflow_db):
    client = TestClient(create_app())
    generated_cases = [_create_stock_review(client)]
    review_date = generated_cases[0]["review_date"]

    matched_response = client.get(f"/api/v1/review/cases?review_date={review_date}")
    empty_response = client.get("/api/v1/review/cases?review_date=1999-01-01")

    assert matched_response.status_code == 200
    assert matched_response.json()["cases"] == generated_cases
    assert empty_response.status_code == 200
    assert empty_response.json() == {"cases": []}
