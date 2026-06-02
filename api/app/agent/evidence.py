"""Agent evidence collector — aggregates data source info from tool results."""

from __future__ import annotations

from typing import Any


class EvidenceCollector:
    """Collects data source metadata across tool calls in one agent turn."""

    def __init__(self) -> None:
        self._sources: list[dict[str, Any]] = []

    def add(self, tool_name: str, data_sources: tuple[str, ...] | list[str]) -> None:
        sources = list(data_sources) if data_sources else []
        if sources:
            self._sources.append({
                "tool": tool_name,
                "data_sources": sources,
            })

    def to_text(self) -> str:
        if not self._sources:
            return ""

        lines = ["## 本轮使用数据"]
        seen = set()
        for src in self._sources:
            key = src["tool"] + "".join(src["data_sources"])
            if key in seen:
                continue
            seen.add(key)
            labels = _source_labels(src["data_sources"])
            lines.append(f"- {src['tool']} → {', '.join(labels)}")
        return "\n".join(lines)

    @property
    def has_data(self) -> bool:
        return bool(self._sources)


_source_label_map = {
    "local_market": "本地行情",
    "workflow": "工作流",
    "agent_memory": "Agent 记忆",
    "external_cache": "外部数据",
}


def _source_labels(sources: list[str]) -> list[str]:
    return [_source_label_map.get(s, s) for s in sources]
