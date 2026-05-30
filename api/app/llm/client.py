from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMUnavailable(Exception):
    """Raised when the optional LLM provider is not configured or unavailable."""


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def complete(self, prompt: str) -> str:
        if not self.is_configured:
            raise LLMUnavailable(
                "LLM 未配置：需要 ALPHAAGENTS_LLM_API_KEY 和 ALPHAAGENTS_LLM_MODEL"
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AlphaAgents 的 A 股投研助手，只做投研、复盘、分析和决策辅助，"
                        "不得输出交易指令或下单建议。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise LLMUnavailable(f"LLM HTTP {exc.code}: {detail[:300]}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(f"LLM 调用失败：{exc}") from exc

        return _message_content(raw_payload)


def _message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMUnavailable("LLM 响应缺少 choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise LLMUnavailable("LLM 响应缺少 message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMUnavailable("LLM 响应为空")
    return content.strip()
