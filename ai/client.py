"""AI client compatible with Alibaba Bailian (DashScope) and OpenAI-compatible APIs."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AIClient:
    """Unified AI client that works with Bailian/DashScope and any OpenAI-compatible API.

    Alibaba Bailian uses the OpenAI-compatible endpoint:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    Usage:
        client = AIClient(
            api_key="sk-xxx",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-max",
        )
        response = client.chat("帮我写一篇关于 AI 的文章")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "qwen-max",
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def chat(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> str:
        """Send a chat completion request and return the response text."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return self.chat_messages(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    def chat_messages(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> str:
        """Send a multi-turn chat completion request."""
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        logger.debug("AI request: model=%s, messages=%d", payload["model"], len(messages))

        resp = self._http.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        logger.debug("AI response: %d chars", len(content))
        return content

    def chat_json(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any] | list[Any]:
        """Send a chat request and parse the response as JSON."""
        raw = self.chat(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            response_format="json",
        )
        # Handle cases where response is wrapped in markdown code blocks
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # remove opening ```json or ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        return json.loads(cleaned)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
