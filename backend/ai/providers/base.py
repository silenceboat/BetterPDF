"""Abstract base class for AI providers."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key
        self.base_url = self._normalize_base_url(base_url)

    @abstractmethod
    def chat(self, messages: list[dict], model: str) -> str: ...

    @staticmethod
    @abstractmethod
    def default_model() -> str: ...

    @staticmethod
    @abstractmethod
    def env_key() -> str: ...

    def supports_tools(self) -> bool:
        return False

    def chat_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list,
        max_iterations: int = 5,
    ) -> str:
        """Default: ignore tools and fall back to plain chat."""
        return self.chat(messages, model)

    def validate(self) -> tuple[bool, str]:
        resolved = self.resolve_api_key()
        if not resolved:
            return False, f"Missing API key. Set it in Settings or {self.env_key()}"
        return True, ""

    def resolve_api_key(self) -> str:
        return self.api_key or os.getenv(self.env_key(), "")

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        return str(base_url or "").strip().rstrip("/")
