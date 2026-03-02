"""Ollama provider."""

from __future__ import annotations

import os

from .base import BaseProvider


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self.base_url = base_url
        self.api_key = api_key

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
