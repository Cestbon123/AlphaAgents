from __future__ import annotations

from copy import deepcopy
from typing import Any


ZHIXING_STRATEGY_ID = "zhixing_trend"

DEFAULT_ZHIXING_PARAMS: dict[str, Any] = {
    "j_max": 13.0,
    "amplitude_max_pct": 4.0,
    "change_min_pct": -2.0,
    "change_max_pct": 1.8,
}


def default_strategy_configs() -> list[dict[str, Any]]:
    return [default_zhixing_strategy_config()]


def default_zhixing_strategy_config() -> dict[str, Any]:
    return {
        "id": ZHIXING_STRATEGY_ID,
        "name": "知行趋势线",
        "enabled": True,
        "engine": "python",
        "description": (
            "基于本地日线、KDJ J 值、知行趋势线、多空线、当日振幅和涨跌幅的"
            "结构化选股策略。不是通达信公式运行时。"
        ),
        "params": deepcopy(DEFAULT_ZHIXING_PARAMS),
        "rules": [
            {"key": "kdj_j", "label": "KDJ J 值", "expected": "<= j_max"},
            {
                "key": "short_trend",
                "label": "短期趋势线",
                "expected": "> 知行多空线",
            },
            {
                "key": "amplitude_pct",
                "label": "当日振幅",
                "expected": "<= amplitude_max_pct",
            },
            {
                "key": "change_pct",
                "label": "当日涨跌幅",
                "expected": "change_min_pct ~ change_max_pct",
            },
            {
                "key": "default_exclusions",
                "label": "默认排除",
                "expected": "创业板、科创板、北交所、ST 等风险标记",
            },
        ],
    }


def merge_strategy_config(
    stored_config: dict[str, Any] | None,
    *,
    strategy_id: str = ZHIXING_STRATEGY_ID,
) -> dict[str, Any]:
    if strategy_id != ZHIXING_STRATEGY_ID:
        raise KeyError(strategy_id)

    config = default_zhixing_strategy_config()
    if not stored_config:
        return config

    if "enabled" in stored_config:
        config["enabled"] = bool(stored_config["enabled"])
    config["params"] = normalize_zhixing_params(
        {
            **config["params"],
            **dict(stored_config.get("params") or {}),
        }
    )
    return config


def normalize_zhixing_params(params: dict[str, Any]) -> dict[str, float]:
    normalized = deepcopy(DEFAULT_ZHIXING_PARAMS)
    for key in normalized:
        if key in params:
            normalized[key] = float(params[key])
    return normalized


def strategy_config_update(
    current: dict[str, Any],
    *,
    enabled: bool | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = merge_strategy_config(current)
    if enabled is not None:
        updated["enabled"] = bool(enabled)
    if params is not None:
        updated["params"] = normalize_zhixing_params({**updated["params"], **params})
    return updated


def template_strategy_draft(prompt: str) -> dict[str, Any]:
    config = default_zhixing_strategy_config()
    lowered = prompt.lower()
    if "严格" in prompt or "保守" in prompt or "strict" in lowered:
        config["params"]["j_max"] = 10.0
        config["params"]["amplitude_max_pct"] = 3.0
        config["params"]["change_max_pct"] = 1.2
    if "宽松" in prompt or "激进" in prompt or "aggressive" in lowered:
        config["params"]["j_max"] = 18.0
        config["params"]["amplitude_max_pct"] = 6.0
        config["params"]["change_max_pct"] = 3.0
    config["name"] = "AI 草稿：知行趋势线"
    config["enabled"] = False
    config["generation_mode"] = "template"
    config["prompt"] = prompt
    return config
