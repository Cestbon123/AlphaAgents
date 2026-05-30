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


def test_deposition_candidates_api_returns_empty_list(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/deposition/candidates")

    assert response.status_code == 200
    assert response.json() == {"candidates": []}


def _create_stock_deposition(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/stocks/000001/depositions",
        json={
            "kind": "风险提醒",
            "title": "确认前保持观察",
            "content": "个股复盘后手动沉淀，不再由每日复盘批量生成。",
        },
    )
    assert response.status_code == 200
    return response.json()["deposition_candidate"]


def test_stock_deposition_persists_candidate(isolated_workflow_db):
    first_client = TestClient(create_app())
    candidate = _create_stock_deposition(first_client)

    second_client = TestClient(create_app())
    response = second_client.get("/api/v1/deposition/candidates")

    assert response.status_code == 200
    assert response.json()["candidates"] == [candidate]


def test_deposition_candidate_api_updates_content_and_status(isolated_workflow_db):
    client = TestClient(create_app())
    candidate = _create_stock_deposition(client)
    candidate_id = candidate["id"]

    update_response = client.patch(
        f"/api/v1/deposition/candidates/{candidate_id}",
        json={
            "title": "确认后的案例标题",
            "content": "人工修订后的沉淀内容",
            "status": "已确认",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["candidate"] == {
        **candidate,
        "title": "确认后的案例标题",
        "content": "人工修订后的沉淀内容",
        "status": "已确认",
    }
    assert client.get("/api/v1/deposition/candidates").json()["candidates"][0]["status"] == "已确认"


def test_confirmed_deposition_entries_api_returns_only_confirmed_items(isolated_workflow_db):
    client = TestClient(create_app())
    candidate = _create_stock_deposition(client)
    confirmed_id = candidate["id"]

    client.patch(
        f"/api/v1/deposition/candidates/{confirmed_id}",
        json={"status": "已确认"},
    )

    response = client.get("/api/v1/deposition/knowledge-entries")

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [entry["id"] for entry in entries] == [confirmed_id]
    assert entries[0]["status"] == "已确认"
    assert entries[0]["content"]


def test_deposition_candidate_api_returns_404_for_unknown_id(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.patch(
        "/api/v1/deposition/candidates/missing",
        json={"status": "已确认"},
    )

    assert response.status_code == 404
