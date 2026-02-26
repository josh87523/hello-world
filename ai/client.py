"""AI client using Anthropic Claude API."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


class AIClient:
    """Claude AI client via Anthropic SDK.

    Usage:
        client = AIClient(api_key="sk-ant-xxx")
        response = client.chat("帮我写一篇关于 AI 的文章")
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def chat(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a message and return the response text."""
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        logger.debug("AI request: model=%s", kwargs["model"])

        resp = self._client.messages.create(**kwargs)
        content = resp.content[0].text

        logger.debug("AI response: %d chars", len(content))
        return content

    def chat_messages(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a multi-turn conversation."""
        # Anthropic API uses separate system param, not in messages
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system:
            kwargs["system"] = system

        resp = self._client.messages.create(**kwargs)
        return resp.content[0].text

    def chat_json(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any] | list[Any]:
        """Send a request and parse the response as JSON."""
        # Append JSON instruction to system prompt
        json_system = system
        if json_system:
            json_system += "\n\n"
        json_system += "你必须只返回有效的JSON，不要包含任何其他文字、解释或markdown代码块。"

        raw = self.chat(
            prompt=prompt,
            system=json_system,
            model=model,
            temperature=temperature,
        )

        # Clean up: strip markdown code blocks if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # remove opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        return json.loads(cleaned)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
