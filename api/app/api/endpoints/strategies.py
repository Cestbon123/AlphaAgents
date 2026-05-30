from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.llm.client import LLMUnavailable, OpenAICompatibleClient
from app.repositories.sqlite import SQLiteWorkflowRepository
from app.strategies.config import (
    ZHIXING_STRATEGY_ID,
    default_strategy_configs,
    merge_strategy_config,
    strategy_config_update,
    template_strategy_draft,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyUpdateInput(BaseModel):
    enabled: bool | None = None
    params: dict[str, Any] | None = None


class StrategyDraftInput(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


@router.get("")
def list_strategies():
    repository = _repository()
    strategies = [
        merge_strategy_config(
            repository.get_strategy_config(strategy["id"]),
            strategy_id=strategy["id"],
        )
        for strategy in default_strategy_configs()
    ]
    return {"strategies": strategies}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    if strategy_id != ZHIXING_STRATEGY_ID:
        raise HTTPException(status_code=404, detail="Strategy not found")
    repository = _repository()
    return {
        "strategy": merge_strategy_config(
            repository.get_strategy_config(strategy_id),
            strategy_id=strategy_id,
        )
    }


@router.patch("/{strategy_id}")
def update_strategy(strategy_id: str, payload: StrategyUpdateInput):
    if strategy_id != ZHIXING_STRATEGY_ID:
        raise HTTPException(status_code=404, detail="Strategy not found")
    repository = _repository()
    current = merge_strategy_config(repository.get_strategy_config(strategy_id))
    updated = strategy_config_update(
        current,
        enabled=payload.enabled,
        params=payload.params,
    )
    saved = repository.save_strategy_config(updated)
    return {"strategy": merge_strategy_config(saved)}


@router.post("/draft")
def draft_strategy(payload: StrategyDraftInput):
    draft = _llm_strategy_draft(payload.prompt)
    return {"strategy": draft}


def _repository() -> SQLiteWorkflowRepository:
    return SQLiteWorkflowRepository(get_settings().workflow_db)


def _llm_strategy_draft(prompt: str) -> dict[str, Any]:
    settings = get_settings()
    client = OpenAICompatibleClient(
        api_key=settings.resolved_llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    if not client.is_configured:
        return template_strategy_draft(prompt)

    llm_prompt = f"""
请把下面的自然语言选股想法转换为 AlphaAgents 当前可执行的结构化策略草稿。
当前仅支持基于“知行趋势线”的参数化 Python 执行器，不支持运行通达信公式、Python 代码或交易指令。
只返回 JSON，不要 Markdown。

输出字段：
{{
  "id": "zhixing_trend",
  "name": "AI 草稿：知行趋势线",
  "enabled": false,
  "engine": "python",
  "description": "一句话说明",
  "params": {{
    "j_max": 数字,
    "amplitude_max_pct": 数字,
    "change_min_pct": 数字,
    "change_max_pct": 数字
  }},
  "rules": []
}}

用户想法：
{prompt}
""".strip()
    try:
        response_text = client.complete(llm_prompt)
        parsed = _extract_json_object(response_text)
        return strategy_config_update(
            merge_strategy_config(parsed),
            enabled=False,
            params=dict(parsed.get("params") or {}),
        )
    except (LLMUnavailable, ValueError, TypeError, json.JSONDecodeError):
        return template_strategy_draft(prompt)


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Strategy draft must be a JSON object")
    parsed["id"] = ZHIXING_STRATEGY_ID
    return parsed
