"""OpenAI / OpenAI-compatible provider."""

from __future__ import annotations

from typing import Any

from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        super().__init__(api_key, base_url)
        self._client = None
        self._initialized = False

    @staticmethod
    def default_model() -> str:
        return "gpt-4o-mini"

    @staticmethod
    def env_key() -> str:
        return "OPENAI_API_KEY"

    def _ensure_client(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        resolved_key = self.resolve_api_key()
        if not resolved_key:
            return
        try:
            import openai
            kwargs: dict[str, Any] = {"api_key": resolved_key}
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
