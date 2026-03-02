"""Anthropic provider (raw requests, no SDK dependency)."""

from __future__ import annotations

import os
from typing import Any

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "") -> None:
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages: list[dict], model: str) -> str:
        import requests

        if not self.api_key:
            raise ValueError("Anthropic API key is missing. Set it in Settings or ANTHROPIC_API_KEY.")

        base = self.base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        endpoint = base.rstrip("/") + "/v1/messages"

        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []
        for item in messages:
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "")
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                conversation.append({"role": role, "content": content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        blocks = data.get("content") or []
        text_parts = [
            str(block.get("text") or "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        merged = "\n".join(part for part in text_parts if part).strip()
        if not merged:
            raise RuntimeError("Anthropic response did not include text content.")
        return merged
