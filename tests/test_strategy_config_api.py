from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_strategy_config_api_lists_and_persists_zhixing_params(tmp_path, monkeypatch):
    workflow_db = tmp_path / "workflows.db"
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("ALPHAAGENTS_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()
    client = TestClient(create_app())

    list_response = client.get("/api/v1/strategies")
    update_response = client.patch(
        "/api/v1/strategies/zhixing_trend",
        json={"enabled": False, "params": {"j_max": 9, "amplitude_max_pct": 3.5}},
    )
    get_response = client.get("/api/v1/strategies/zhixing_trend")

    assert list_response.status_code == 200
    assert list_response.json()["strategies"][0]["id"] == "zhixing_trend"
    assert update_response.status_code == 200
    assert update_response.json()["strategy"]["enabled"] is False
    assert get_response.status_code == 200
    strategy = get_response.json()["strategy"]
    assert strategy["params"]["j_max"] == 9.0
    assert strategy["params"]["amplitude_max_pct"] == 3.5


def test_strategy_draft_api_returns_safe_template_without_llm_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHAAGENTS_WORKFLOW_DB", str(tmp_path / "workflows.db"))
    monkeypatch.setenv("ALPHAAGENTS_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/strategies/draft",
        json={"prompt": "更保守一点，振幅小，J 值更低"},
    )

    assert response.status_code == 200
    strategy = response.json()["strategy"]
    assert strategy["id"] == "zhixing_trend"
    assert strategy["enabled"] is False
    assert strategy["params"]["j_max"] <= 13.0
    assert strategy["generation_mode"] == "template"
