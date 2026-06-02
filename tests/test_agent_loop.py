import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from app.agent.agent_loop import AgentContext, _call_tool, run_agent_loop_sync
from app.agent.memory_repository import AgentMemoryRepository


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _FakeLlm:
    model = "fake-model"
    base_url = "https://example.test"
    api_key = "test-key"
    timeout_seconds = 1


def _message(content="", tool_calls=None):
    return {
        "choices": [{
            "message": {
                "content": content,
                "tool_calls": tool_calls or [],
            }
        }]
    }


def test_agent_loop_streams_tool_events_and_stores_tool_call_id(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        session_id = repo.create_session()
        context = AgentContext(session_id=session_id, memory=repo)

        responses = [
            _message(tool_calls=[{
                "id": "call_alerts",
                "type": "function",
                "function": {"name": "get_alerts", "arguments": "{\"symbol\":\"000001\"}"},
            }]),
            _message(content="已经查看提醒。"),
        ]

        monkeypatch.setattr(
            "app.agent.agent_loop.urlopen",
            lambda request, timeout: _FakeResponse(responses.pop(0)),
        )
        monkeypatch.setattr(
            "app.agent.agent_loop.build_tools_for_llm",
            lambda: [],
        )
        monkeypatch.setattr(
            "app.agent.agent_loop.find_tool",
            lambda name: SimpleNamespace(handler=lambda **kwargs: {"ok": True}),
        )

        events = list(run_agent_loop_sync("看一下 000001", context, _FakeLlm()))
        names = [event.split("\n", 1)[0] for event in events]

        assert names.index("event: tool_start") < names.index("event: tool_result")
        assert names[-1] == "event: done"

        messages = repo.get_session_messages(session_id)
        tool_messages = [msg for msg in messages if msg["role"] == "tool"]
        assert tool_messages[0]["tool_call_id"] == "call_alerts"
        repo.close()


def test_agent_loop_replays_tool_call_ids_in_history(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        session_id = repo.create_session()
        tool_calls = [{
            "id": "call_history",
            "type": "function",
            "function": {"name": "get_alerts", "arguments": "{\"symbol\":\"000001\"}"},
        }]
        repo.add_message(session_id, "user", content="第一轮")
        repo.add_message(
            session_id,
            "assistant",
            content="",
            tool_calls=json.dumps(tool_calls, ensure_ascii=False),
        )
        repo.add_message(
            session_id,
            "tool",
            content="{\"ok\": true}",
            tool_call_id="call_history",
            tool_name="get_alerts",
        )

        captured_payloads = []

        def fake_urlopen(request, timeout):
            captured_payloads.append(json.loads(request.data.decode("utf-8")))
            return _FakeResponse(_message(content="继续分析。"))

        monkeypatch.setattr("app.agent.agent_loop.urlopen", fake_urlopen)
        monkeypatch.setattr(
            "app.agent.agent_loop.build_tools_for_llm",
            lambda: [],
        )

        context = AgentContext(session_id=session_id, memory=repo)
        list(run_agent_loop_sync("第二轮", context, _FakeLlm()))

        replayed = captured_payloads[0]["messages"]
        assert any(
            msg.get("role") == "tool" and msg.get("tool_call_id") == "call_history"
            for msg in replayed
        )
        repo.close()


def test_write_tool_requires_confirmation(monkeypatch):
    called = False

    def handler(**kwargs):
        nonlocal called
        called = True
        return {"status": "written"}

    monkeypatch.setattr(
        "app.agent.agent_loop.find_tool",
        lambda name: SimpleNamespace(handler=handler, requires_confirmation=True),
    )

    result = _call_tool("record_operation", {"symbol": "000001.SZ"})

    assert result["requires_confirmation"] is True
    assert called is False


def test_agent_loop_honors_requested_skill_id(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        session_id = repo.create_session()
        context = AgentContext(
            session_id=session_id,
            memory=repo,
            current_symbol="000001.SH",
        )

        monkeypatch.setattr(
            "app.agent.agent_loop.urlopen",
            lambda request, timeout: _FakeResponse(_message(content="已按指定技能处理。")),
        )
        monkeypatch.setattr(
            "app.agent.agent_loop.build_tools_for_llm",
            lambda: [],
        )

        events = list(
            run_agent_loop_sync(
                "帮我看一下这只股",
                context,
                _FakeLlm(),
                requested_skill_id="history_review",
            )
        )

        selected_event = next(event for event in events if event.startswith("event: skill_selected"))
        payload = json.loads(selected_event.split("data: ", 1)[1])
        assert payload["skills"] == ["history_review"]
        repo.close()
