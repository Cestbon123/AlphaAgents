import asyncio
import tempfile
from pathlib import Path

from app.agent.memory_curator import curate_session_memory
from app.agent.memory_repository import AgentMemoryRepository


class _CuratorLlm:
    def complete(self, prompt: str) -> str:
        return """
        {
          "decisions": [{
            "symbol": "000001.SZ",
            "decision_type": "watch",
            "conclusion": "等待趋势重新转强",
            "source": "agent_chat"
          }],
          "impressions": [{
            "symbol": "000001.SZ",
            "status": "watching",
            "impression": "短期仍需观察"
          }],
          "profile_updates": [{
            "key": "risk_preference",
            "value": "稳健"
          }]
        }
        """


def test_curator_closes_session_and_persists_memory():
    with tempfile.TemporaryDirectory() as tmp:
        repo = AgentMemoryRepository(Path(tmp) / "test.db")
        session_id = repo.create_session()
        repo.add_message(session_id, "user", content="000001 先观察，不追高。")
        repo.add_message(session_id, "assistant", content="可以，等待趋势重新转强。")

        asyncio.run(curate_session_memory(session_id, repo, _CuratorLlm()))

        sessions = repo.list_sessions()
        assert sessions[0]["ended_at"]
        assert sessions[0]["summary"]
        assert repo.get_decisions_for_symbol("000001.SZ")[0]["decision_type"] == "watch"
        assert repo.get_impression("000001.SZ")["status"] == "watching"
        assert repo.get_profile_key("risk_preference") == "稳健"
        repo.close()
