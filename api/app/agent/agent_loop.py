"""Agent loop: LLM orchestration with tool calling and SSE events.

All LLM calls are synchronous and blocking; callers should run this generator
outside the event loop.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib.request import Request, urlopen

from app.agent.evidence import EvidenceCollector
from app.agent.memory_repository import AgentMemoryRepository
from app.agent.skills import build_skill_prompt, get_skill, select_skills
from app.agent.tools import build_tools_for_llm, find_tool

MAX_TURNS = 5

ROLE_PROMPT = """你是 AlphaAgents，一个个人 A 股投研助手。
你只做投研、复盘、分析和决策辅助，不得输出交易指令或下单建议。"""

DATA_POLICY_PROMPT = """## 数据使用规则
- 涉及股票价格、走势、指标、破位等，必须通过工具获取本地行情数据，不得凭模型常识编造
- 涉及历史操作、复盘、判断，必须通过工具查询工作流记录或 Agent 记忆
- 所有关键数据应说明来源（本地行情/工作流/记忆/外部数据）
- 数据缺失时明确说明缺口，不得用模糊语言补全"""

OUTPUT_POLICY_PROMPT = """## 回答格式要求
对于投研分析类问题，请按以下结构回答：

**结论**
- 用 1-3 句话概括核心判断

**依据**
- 说明每条关键数据来自哪个工具、最新日期是什么
- 例如：“本地行情(2026-06-03)：收盘 15.10，知行多空线 15.20”
- 例如：“历史记忆：2026-05-28 你判断「等待回踩多空线」”

**需要注意**
- 列出数据缺口、不确定性、以及你不能做的事情

## 写入规则
- 任何写入操作（记录操作、保存复盘、更新跟踪状态、更新画像）必须先生成预览请用户确认
- 用户说「确认」「可以」「保存」等明确同意后再执行写入
- 用户说「不要」「算了」「取消」则放弃本次写入"""

CONFIRM_RULE_PROMPT = """## 写入确认规则（最重要）
当用户要求写入（记录操作、保存复盘、更新跟踪状态、更新用户画像）时，你必须：
1. 先生成待写入的内容预览
2. 明确询问用户是否确认
3. 等待用户说「确认」「可以」「行」「保存」后再调用写入工具
4. 如果用户说「不要」「算了」「取消」，放弃操作
绝对不能：先生成预览、不等用户确认就直接调用写入工具。"""


class AgentContext:
    __slots__ = (
        "session_id", "memory", "current_symbol",
        "profile_text", "impressions_text", "decisions_text",
        "current_view", "data_hints",
    )

    def __init__(
        self,
        session_id: str,
        memory: AgentMemoryRepository,
        current_symbol: str | None = None,
        profile_text: str = "",
        impressions_text: str = "",
        decisions_text: str = "",
        current_view: str | None = None,
        data_hints: dict[str, object] | None = None,
    ):
        self.session_id = session_id
        self.memory = memory
        self.current_symbol = current_symbol
        self.profile_text = profile_text
        self.impressions_text = impressions_text
        self.decisions_text = decisions_text
        self.current_view = current_view
        self.data_hints = data_hints or {}


def run_agent_loop_sync(
    user_message: str,
    context: AgentContext,
    llm_client: Any,
    requested_skill_id: str | None = None,
) -> Iterator[str]:
    """Run one agent turn synchronously and yield SSE event strings as they happen."""

    def emit(event_name: str, data: dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event_name}\ndata: {payload}\n\n"

    selected = (
        [requested_skill_id]
        if requested_skill_id and get_skill(requested_skill_id)
        else select_skills(user_message, context.current_symbol, context.current_view)
    )
    yield emit("skill_selected", {"skills": selected})
    evidence = EvidenceCollector()
    system = _build_system_prompt(context, selected)
    messages = _build_messages_from_history(context, system)

    messages.append({"role": "user", "content": user_message})
    context.memory.add_message(context.session_id, "user", content=user_message)

    tools = build_tools_for_llm()

    for _ in range(MAX_TURNS):
        payload = {
            "model": llm_client.model,
            "messages": messages,
            "temperature": 0.3,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
        }

        try:
            request_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = Request(
                f"{llm_client.base_url}/chat/completions",
                data=request_data,
                headers={
                    "Authorization": f"Bearer {llm_client.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            resp = urlopen(req, timeout=llm_client.timeout_seconds)
            body = resp.read().decode("utf-8")
            result = json.loads(body)
        except Exception as exc:
            yield emit("error", {"error": f"LLM 调用失败: {exc}"})
            break

        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        if content.strip():
            yield emit("delta", {"content": content})

        if tool_calls:
            _normalize_tool_calls(tool_calls)
            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": tool_calls,
            })
            context.memory.add_message(
                context.session_id,
                "assistant",
                content=content or "",
                tool_calls=json.dumps(tool_calls, ensure_ascii=False),
            )

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                call_id = tc["id"]
                args = _parse_tool_args(tc)
                tool = find_tool(tool_name)
                data_sources = tuple(getattr(tool, "data_sources", ()) or ())
                is_write = bool(getattr(tool, "is_write", False))
                requires_confirmation = bool(getattr(tool, "requires_confirmation", False))

                tool_meta = {
                    "name": tool_name, "arguments": args,
                    "data_sources": list(data_sources),
                    "is_write": is_write,
                    "requires_confirmation": requires_confirmation,
                }
                yield emit("tool_start", tool_meta)
                tool_result = _call_tool(tool_name, args)
                if data_sources:
                    evidence.add(tool_name, data_sources)
                yield emit("tool_result", {"name": tool_name, "result": tool_result})

                result_json = json.dumps(tool_result, ensure_ascii=False, default=str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result_json,
                })
                context.memory.add_message(
                    context.session_id,
                    "tool",
                    content=result_json,
                    tool_call_id=call_id,
                    tool_name=tool_name,
                )
            continue

        if content.strip():
            context.memory.add_message(context.session_id, "assistant", content=content)
        if evidence.has_data:
            yield emit("evidence", {"text": evidence.to_text()})
        yield emit("done", {"session_id": context.session_id})
        return

    if evidence.has_data:
        yield emit("evidence", {"text": evidence.to_text()})
    yield emit("done", {"session_id": context.session_id})


def _build_system_prompt(context: AgentContext, selected_skills: list[str] | None = None) -> str:
    parts = [
        ROLE_PROMPT,
        "",
        DATA_POLICY_PROMPT,
        "",
        OUTPUT_POLICY_PROMPT,
        "",
        CONFIRM_RULE_PROMPT,
        "",
        build_skill_prompt(selected_skills),
    ]
    if context.profile_text:
        parts.append(f"## 用户画像\n{context.profile_text}")
    if context.impressions_text:
        parts.append(f"## 当前关注股票\n{context.impressions_text}")
    if context.decisions_text:
        parts.append(f"## 相关历史决策\n{context.decisions_text}")
    if context.current_symbol:
        parts.append(f"## 当前界面股票\n用户正在查看: {context.current_symbol}")
    if context.current_view and context.current_view != "chat":
        parts.append(f"## 当前界面\n用户当前页面: {context.current_view}")
    if context.data_hints:
        hint_lines = [f"- {key}: {value}" for key, value in context.data_hints.items()]
        parts.append("## 当前界面状态\n" + "\n".join(hint_lines))
    return "\n\n".join(parts)


def _build_messages_from_history(
    context: AgentContext,
    system: str,
) -> list[dict[str, Any]]:
    history = context.memory.get_session_messages(context.session_id, limit=30)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    pending_tool_call_ids: list[str] = []

    for msg in history:
        role = msg["role"]
        if role == "tool":
            tool_call_id = msg.get("tool_call_id")
            if tool_call_id and tool_call_id in pending_tool_call_ids:
                pending_tool_call_ids.remove(tool_call_id)
            if not tool_call_id and pending_tool_call_ids:
                tool_call_id = pending_tool_call_ids.pop(0)
            if not tool_call_id:
                continue
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": msg.get("content") or "",
            })
            continue

        item: dict[str, Any] = {"role": role, "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            try:
                tool_calls = json.loads(msg["tool_calls"])
            except json.JSONDecodeError:
                tool_calls = []
            if tool_calls:
                item["tool_calls"] = tool_calls
                pending_tool_call_ids.extend(
                    tc.get("id") or f"call_legacy_{i}"
                    for i, tc in enumerate(tool_calls)
                )
        messages.append(item)

    return messages


def _normalize_tool_calls(tool_calls: list[dict[str, Any]]) -> None:
    for i, tc in enumerate(tool_calls):
        if not tc.get("id"):
            tc["id"] = f"call_{i}"
        if "type" not in tc:
            tc["type"] = "function"


def _parse_tool_args(tool_call: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(tool_call["function"]["arguments"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return {}


def _call_tool(tool_name: str, args: dict[str, Any]) -> Any:
    tool = find_tool(tool_name)
    if tool is None:
        return {"error": f"未知工具: {tool_name}"}
    confirmed = args.pop("confirmed", False)
    if bool(getattr(tool, "requires_confirmation", False)) and confirmed is not True:
        return {
            "requires_confirmation": True,
            "tool": tool_name,
            "arguments": args,
            "message": "该操作会写入本地记录，需要用户明确确认后再执行。",
        }
    try:
        return tool.handler(**args)
    except Exception as exc:
        return {"error": str(exc)}
