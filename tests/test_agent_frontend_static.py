from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_frontend_uses_shared_api_client_for_history():
    app_js = (ROOT / "frontend/scripts/app.js").read_text(encoding="utf-8")
    api_js = (ROOT / "frontend/scripts/api.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/styles/app.css").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8000/api/v1/agent" not in app_js
    assert "AlphaAgentsApi.listAgentSessions" in app_js
    assert "AlphaAgentsApi.getAgentSession" in app_js
    assert "AlphaAgentsApi.deleteAgentSession" in app_js
    assert "method: \"DELETE\"" in api_js
    assert ".history-delete" in css
    assert "deleteHistorySession" in app_js


def test_agent_frontend_renders_assistant_text_without_inner_html():
    app_js = (ROOT / "frontend/scripts/app.js").read_text(encoding="utf-8")

    assert 'el.innerHTML = text.replace(/\\n/g, "<br>");' not in app_js
    assert "el.textContent = text;" in app_js


def test_agent_frontend_shows_write_confirmation_notice():
    app_js = (ROOT / "frontend/scripts/app.js").read_text(encoding="utf-8")

    assert "requires_confirmation" in app_js
    assert "该操作需要确认后执行" in app_js

def test_agent_frontend_supports_slash_skill_picker_and_token_display():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "frontend/scripts/app.js").read_text(encoding="utf-8")
    api_js = (ROOT / "frontend/scripts/api.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/styles/app.css").read_text(encoding="utf-8")

    assert 'id="agent-skill-menu"' in html
    assert 'id="agent-selected-skill"' in html
    assert "输入 / 选技能" in html
    assert "renderAgentSkillMenu" in app_js
    assert "selectedAgentSkill" in app_js
    assert "requestedSkill?.id" in app_js
    assert "activeAgentSkillIndex" in app_js
    assert "ArrowDown" in app_js
    assert "ArrowUp" in app_js
    assert "setActiveAgentSkillOption(0)" in app_js
    assert "body.requested_skill_id" in api_js
    assert ".agent-skill-token" in css
    assert ".agent-skill-option" in css
    assert ".agent-skill-option.is-active" in css
    assert "input.has-skill" not in css
