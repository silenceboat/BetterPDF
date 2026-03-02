"""OpenAI / OpenAI-compatible provider."""

from __future__ import annotations

from typing import Any, Optional

from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
        self._initialized = False

    def _ensure_client(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        if not self.api_key:
            return
        try:
            import openai
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = openai.OpenAI(**kwargs)
        except ImportError:
            pass

    def chat(self, messages: list[dict], model: str) -> str:
        self._ensure_client()
        if not self._client:
            raise RuntimeError("OpenAI client not available. Check api_key and openai package.")
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        return response.choices[0].message.content
