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


def test_review_operations_api_returns_empty_list_without_records(isolated_workflow_db):
    client = TestClient(create_app())

    response = client.get("/api/v1/review/operations", params={"operation_date": "2026-05-12"})

    assert response.status_code == 200
    assert response.json() == {"operations": []}


def test_review_operations_api_replaces_normalizes_and_persists_by_date(isolated_workflow_db):
    first_client = TestClient(create_app())

    save_response = first_client.put(
        "/api/v1/review/operations",
        json={
            "operation_date": "2026-05-12",
            "operations": [
                {
                    "symbol": " sz000001 ",
                    "name": "平安银行",
                    "source": "manual",
                    "system_conclusion": "关注",
                    "user_action": "买入",
                    "reason": "回踩确认",
                    "result_summary": "收盘小幅上涨",
                },
                {
                    "symbol": "sh600000",
                    "user_action": "未操作",
                },
            ],
        },
    )

    assert save_response.status_code == 200
    assert save_response.json() == {
        "operations": [
            {
                "operation_date": "2026-05-12",
                "symbol": "SZ000001",
                "name": "平安银行",
                "source": "manual",
                "system_conclusion": "关注",
                "user_action": "买入",
                "reason": "回踩确认",
                "result_summary": "收盘小幅上涨",
            },
            {
                "operation_date": "2026-05-12",
                "symbol": "SH600000",
                "name": "",
                "source": "manual",
                "system_conclusion": "",
                "user_action": "未操作",
                "reason": "",
                "result_summary": "",
            },
        ]
    }

    second_client = TestClient(create_app())
    read_response = second_client.get(
        "/api/v1/review/operations",
        params={"operation_date": "2026-05-12"},
    )

    assert read_response.status_code == 200
    assert read_response.json() == save_response.json()

    other_date_response = second_client.put(
        "/api/v1/review/operations",
        json={
            "operation_date": "2026-05-13",
            "operations": [
                {
                    "symbol": "000333",
                    "user_action": "观察",
                    "reason": "等待量能",
                }
            ],
        },
    )
    replace_response = second_client.put(
        "/api/v1/review/operations",
        json={
            "operation_date": "2026-05-12",
            "operations": [
                {
                    "symbol": "300750",
                    "user_action": "减仓",
                    "result_summary": "降低波动风险",
                }
            ],
        },
    )

    assert other_date_response.status_code == 200
    assert replace_response.status_code == 200
    assert second_client.get(
        "/api/v1/review/operations",
        params={"operation_date": "2026-05-12"},
    ).json() == {
        "operations": [
            {
                "operation_date": "2026-05-12",
                "symbol": "300750",
                "name": "",
                "source": "manual",
                "system_conclusion": "",
                "user_action": "减仓",
                "reason": "",
                "result_summary": "降低波动风险",
            }
        ]
    }
    assert second_client.get(
        "/api/v1/review/operations",
        params={"operation_date": "2026-05-13"},
    ).json() == other_date_response.json()
