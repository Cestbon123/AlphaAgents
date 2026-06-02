"""Agent chat endpoint — POST /agent/chat with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import queue
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.agent.agent_loop import AgentContext, run_agent_loop_sync
from app.agent.memory_curator import curate_session_memory
from app.agent.memory_repository import AgentMemoryRepository
from app.agent.skills import get_skill, get_skills_for_display
from app.agent.tools import AGENT_TOOLS
from app.core.config import get_settings
from app.llm.client import OpenAICompatibleClient

router = APIRouter(prefix="/agent", tags=["agent"])

_ALLOWED_DATA_HINTS = {"right_panel_open", "active_section", "current_symbol"}


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    symbol: str | None = None
    current_view: str | None = None
    data_hints: dict[str, object] | None = None
    requested_skill_id: str | None = None


def _sanitize_data_hints(data_hints: dict[str, object] | None) -> dict[str, object]:
    if not data_hints:
        return {}
    sanitized: dict[str, object] = {}
    for key in _ALLOWED_DATA_HINTS:
        value = data_hints.get(key)
        if isinstance(value, str):
            sanitized[key] = value[:80]
        elif isinstance(value, bool | int | float):
            sanitized[key] = value
    return sanitized


def _build_llm_client() -> OpenAICompatibleClient | None:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        return None
    return OpenAICompatibleClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=120.0,
    )


def _build_context(
    session_id: str,
    memory: AgentMemoryRepository,
    symbol: str | None,
    current_view: str | None = None,
    data_hints: dict[str, object] | None = None,
) -> AgentContext:
    profile = memory.get_profile()
    profile_parts = []
    for k, v in profile.items():
        label = {
            "risk_preference": "风险偏好",
            "favorite_sectors": "关注板块",
            "strategy_preference": "策略偏好",
        }.get(k, k)
        profile_parts.append(f"- {label}: {v}")
    profile_text = "\n".join(profile_parts) if profile_parts else ""

    impressions = memory.get_all_impressions()
    imp_parts = []
    for imp in impressions[:10]:
        status_label = {
            "tracking": "重点跟踪",
            "holding": "持仓中",
            "broken": "已破位",
            "watching": "关注中",
        }.get(imp.get("status", ""), imp.get("status", ""))
        imp_parts.append(f"- {imp['symbol']} ({status_label}): {imp['impression']}")
    impressions_text = "\n".join(imp_parts) if imp_parts else ""

    decisions = memory.search_decisions("", limit=5)
    dec_parts = []
    for d in decisions:
        sym = d.get("symbol", "") or ""
        typ = d.get("decision_type", "") or ""
        conc = d.get("conclusion", "") or ""
        dec_parts.append(f"- [{d.get('decision_date','')}] {sym} {typ}: {conc}")
    decisions_text = "\n".join(dec_parts) if dec_parts else ""

    return AgentContext(
        session_id=session_id,
        memory=memory,
        current_symbol=symbol,
        profile_text=profile_text,
        impressions_text=impressions_text,
        decisions_text=decisions_text,
        current_view=current_view,
        data_hints=_sanitize_data_hints(data_hints),
    )


@router.post("/chat")
async def agent_chat(body: AgentChatRequest):
    llm = _build_llm_client()
    if llm is None or not llm.is_configured:
        raise HTTPException(status_code=503, detail="LLM 未配置")
    if body.requested_skill_id and not get_skill(body.requested_skill_id):
        raise HTTPException(status_code=400, detail="未知的 Agent Skill")

    db_path = get_settings().data_db
    session_id = body.session_id

    event_queue: queue.Queue[str | None] = queue.Queue()

    def _run_in_thread():
        nonlocal session_id
        memory = AgentMemoryRepository(db_path)
        if not session_id:
            session_id = memory.create_session()
        context = _build_context(
            session_id, memory, body.symbol, body.current_view, body.data_hints
        )
        try:
            for event in run_agent_loop_sync(
                body.message, context, llm, requested_skill_id=body.requested_skill_id
            ):
                event_queue.put(event)
        except Exception as exc:
            event_queue.put(
                f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            )
        finally:
            if session_id:
                try:
                    asyncio.run(curate_session_memory(session_id, memory, llm))
                except Exception:
                    memory.close_session(session_id)
            event_queue.put(None)
            memory.close()

    thread = threading.Thread(target=_run_in_thread, daemon=True)
    thread.start()

    async def event_stream():
        loop = asyncio.get_running_loop()
        while True:
            try:
                event = await loop.run_in_executor(None, lambda: event_queue.get(timeout=0.1))
            except queue.Empty:
                continue
            if event is None:
                return
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def list_sessions(limit: int = 50):
    memory = AgentMemoryRepository(get_settings().data_db)
    try:
        return {"sessions": memory.list_sessions(limit=limit)}
    finally:
        memory.close()


@router.get("/tools")
def list_agent_tools():
    return {
        "tools": [
            {"name": t.name, "description": t.description}
            for t in AGENT_TOOLS
        ]
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    memory = AgentMemoryRepository(get_settings().data_db)
    try:
        msgs = memory.get_session_messages(session_id)
        return {"session_id": session_id, "messages": msgs}
    finally:
        memory.close()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    memory = AgentMemoryRepository(get_settings().data_db)
    try:
        deleted = memory.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Agent session not found")
        return {"session_id": session_id, "deleted": True}
    finally:
        memory.close()


@router.get("/skills")
def list_skills():
    """Return available Agent skills for frontend display."""
    return {"skills": get_skills_for_display()}


@router.get("/profile")
def get_profile():
    memory = AgentMemoryRepository(get_settings().data_db)
    try:
        return {"profile": memory.get_profile()}
    finally:
        memory.close()
