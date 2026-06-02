"""Tests for agent memory schema and repository."""

import tempfile
from pathlib import Path

from app.agent.memory_repository import AgentMemoryRepository
from app.agent.memory_schema import SCHEMA_VERSION, init_agent_memory


def test_schema_init_creates_all_tables():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = init_agent_memory(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "agent_user_profile" in names
        assert "agent_decision_memory" in names
        assert "agent_stock_impressions" in names
        assert "agent_sessions" in names
        assert "agent_messages" in names
        assert "agent_messages_fts" in names
        columns = conn.execute("PRAGMA table_info(agent_messages)").fetchall()
        assert "tool_call_id" in {row["name"] for row in columns}
        v = conn.execute("SELECT version FROM agent_schema_version").fetchone()
        assert v["version"] == SCHEMA_VERSION
        conn.close()


def test_user_profile_crud():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        assert repo.get_profile() == {}
        repo.update_profile("risk_preference", "conservative", source="test")
        assert repo.get_profile_key("risk_preference") == "conservative"
        profile = repo.get_profile()
        assert profile["risk_preference"] == "conservative"
        repo.update_profile("risk_preference", "aggressive")
        assert repo.get_profile_key("risk_preference") == "aggressive"
        repo.close()


def test_decision_memory_add_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        repo.add_decision({
            "symbol": "000001.SH",
            "decision_date": "2026-05-31",
            "decision_type": "skip",
            "conclusion": "破位已放弃，等待回踩确认",
            "outcome": "",
            "source": "agent_chat",
        })
        repo.add_decision({
            "symbol": "000002.SH",
            "decision_date": "2026-05-30",
            "decision_type": "buy",
            "conclusion": "趋势回调到位，J值超卖，分批买入",
            "source": "operation_record",
        })
        results = repo.search_decisions("破位")
        assert len(results) == 1
        assert results[0]["symbol"] == "000001.SH"
        by_sym = repo.get_decisions_for_symbol("000002.SH")
        assert len(by_sym) == 1
        assert by_sym[0]["decision_type"] == "buy"
        repo.close()


def test_stock_impressions_upsert():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        assert repo.get_impression("000001.SH") is None
        repo.upsert_impression("000001.SH", "watching", "低位关注中，等待J值进一步走低")
        imp = repo.get_impression("000001.SH")
        assert imp["status"] == "watching"
        repo.upsert_impression("000001.SH", "broken", "已跌破多空线，放弃")
        imp2 = repo.get_impression("000001.SH")
        assert imp2["status"] == "broken"
        all_imp = repo.get_all_impressions()
        assert len(all_imp) == 1
        repo.close()


def test_sessions_and_messages():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        sid = repo.create_session()
        assert sid
        repo.add_message(sid, "user", content="今天有什么关注的？")
        repo.add_message(sid, "assistant", content="您持仓的000001今日破位。")
        repo.add_message(
            sid,
            "assistant",
            content=None,
            tool_calls='{"name":"get_alerts"}',
            tool_name="get_alerts",
        )
        msgs = repo.get_session_messages(sid)
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[2]["tool_name"] == "get_alerts"
        repo.close_session(sid, summary="用户查看了持仓告警")
        repo.close()


def test_delete_session_removes_messages_and_session():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        sid = repo.create_session()
        repo.add_message(sid, "user", content="delete me")

        assert repo.delete_session(sid) is True
        assert repo.get_session_messages(sid) == []
        assert all(session["id"] != sid for session in repo.list_sessions())
        assert repo.delete_session(sid) is False
        repo.close()


def test_fts_search():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        sid = repo.create_session()
        repo.add_message(sid, "user", content="000001今天破位了吗")
        repo.add_message(
            sid,
            "assistant",
            content="是的，000001 今日收盘15.10，低于知行多空线15.20，已破位。",
        )
        results = repo.search_sessions("破位")
        assert len(results) >= 1
        any_contains = any("破位" in (r.get("content") or "") for r in results)
        assert any_contains
        repo.close()
