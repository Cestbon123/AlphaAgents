"""Agent memory curator — extracts decisions and updates profile after conversations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agent.memory_repository import AgentMemoryRepository


async def curate_session_memory(
    session_id: str,
    memory: AgentMemoryRepository,
    llm_client: Any,
) -> None:
    """Analyze a completed session and persist key decisions, impressions, and profile updates.

    Called after a conversation ends. Uses LLM to extract structured insights
    from the conversation and writes them to the memory tables.
    """
    messages = memory.get_session_messages(session_id, limit=50)
    if not messages:
        return

    conversation = ""
    for m in messages:
        role = m["role"]
        content = m.get("content") or ""
        if role in ("user", "assistant") and content.strip():
            conversation += f"[{role}] {content[:300]}\n"

    if not conversation.strip():
        return

    # Build prompt for LLM
    prompt = f"""Analyze this conversation between a user and their investment assistant.
Extract structured insights in JSON format. Only include fields where you found clear evidence.

Conversation:
{conversation[:4000]}

Return ONLY a JSON object (no markdown, no explanation):
{{
  "decisions": [
    {{
      "symbol": "股票代码",
      "decision_type": "buy|sell|watch|skip",
      "conclusion": "1-2句话总结决策",
      "source": "agent_chat"
    }}
  ],
  "impressions": [
    {{
      "symbol": "股票代码",
      "status": "tracking|holding|broken|watching",
      "impression": "当前印象"
    }}
  ],
  "profile_updates": [
    {{
      "key": "risk_preference|favorite_sectors|strategy_preference",
      "value": "新的偏好值"
    }}
  ]
}}

If nothing to extract, return {{}}."""

    try:
        raw_response = llm_client.complete(prompt)
        # Strip markdown code blocks
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        result = json.loads(cleaned)
    except Exception:
        # LLM response wasn't valid JSON — skip
        # Close the session without memory extraction
        summary = _make_summary(conversation)
        memory.close_session(session_id, summary)
        return

    # Persist decisions
    for decision in result.get("decisions", []):
        if decision.get("symbol") and decision.get("conclusion"):
            memory.add_decision({
                "symbol": decision["symbol"],
                "decision_date": datetime.now(UTC).date().isoformat(),
                "decision_type": decision.get("decision_type", ""),
                "conclusion": decision["conclusion"],
                "source": decision.get("source", "agent_chat"),
            })

    # Update impressions
    for imp in result.get("impressions", []):
        if imp.get("symbol") and imp.get("impression"):
            memory.upsert_impression(
                imp["symbol"],
                imp.get("status", "watching"),
                imp["impression"],
            )

    # Update profile
    for update in result.get("profile_updates", []):
        if update.get("key") and update.get("value"):
            memory.update_profile(update["key"], update["value"], source="agent_chat")

    # Close session with summary
    summary = _make_summary(conversation)
    memory.close_session(session_id, summary)


def _make_summary(conversation: str) -> str:
    """Create a brief session summary from the conversation."""
    lines = conversation.strip().split("\n")
    # Take first few user and assistant messages
    summary_parts = []
    for line in lines[:6]:
        if line.startswith("[user]"):
            summary_parts.append("用户: " + line[7:].strip()[:100])
        elif line.startswith("[assistant]"):
            summary_parts.append("agent: " + line[12:].strip()[:100])
    return " | ".join(summary_parts[:3])
