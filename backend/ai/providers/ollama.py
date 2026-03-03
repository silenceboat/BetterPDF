"""Ollama provider."""

from __future__ import annotations

import os

from .base import BaseProvider


class OllamaProvider(BaseProvider):
    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        super().__init__(api_key, base_url)

    @staticmethod
    def default_model() -> str:
        return "llama3.2"

    @staticmethod
    def env_key() -> str:
        return "OLLAMA_API_KEY"

    def validate(self) -> tuple[bool, str]:
        """Ollama does not require an API key."""
        return True, ""

    def chat(self, messages: list[dict], model: str) -> str:
        import requests

        base = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        endpoint = base.rstrip("/") + "/api/chat"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            endpoint,
            json={
                "model": model,
                "messages": messages,
                "stream": False,
            },
            headers=headers or None,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
