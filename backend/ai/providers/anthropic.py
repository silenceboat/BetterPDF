"""Anthropic provider (raw requests, no SDK dependency)."""

from __future__ import annotations

import json
import os
from typing import Any

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        super().__init__(api_key, base_url)

    @staticmethod
    def default_model() -> str:
        return "claude-3-5-haiku-latest"

    @staticmethod
    def env_key() -> str:
        return "ANTHROPIC_API_KEY"

    def chat(self, messages: list[dict], model: str) -> str:
        import requests

        resolved_key = self.resolve_api_key()
        if not resolved_key:
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
                "x-api-key": resolved_key,
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

    def supports_tools(self) -> bool:
        return True

    def chat_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list,
        max_iterations: int = 5,
    ) -> str:
        import requests

        resolved_key = self.resolve_api_key()
        if not resolved_key:
            raise ValueError("Anthropic API key is missing. Set it in Settings or ANTHROPIC_API_KEY.")

        tool_specs = [t.to_anthropic_spec() for t in tools]
        tools_by_name = {t.name: t for t in tools}

        system_parts: list[str] = []
        conversation: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(str(m.get("content") or ""))
            else:
                conversation.append(m)

        base = self.base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        endpoint = base.rstrip("/") + "/v1/messages"
        headers = {
            "x-api-key": resolved_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        for _ in range(max_iterations):
            payload: dict[str, Any] = {
                "model": model,
                "messages": conversation,
                "tools": tool_specs,
                "tool_choice": {"type": "auto"},
                "max_tokens": 2000,
            }
            if system_parts:
                payload["system"] = "\n\n".join(system_parts)

            resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [])

            if data.get("stop_reason") != "tool_use":
                texts = [
                    str(b.get("text") or "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                merged = "\n".join(t for t in texts if t).strip()
                if not merged:
                    raise RuntimeError("No text content in Anthropic response")
                return merged

            conversation.append({"role": "assistant", "content": content})
            tool_results = []
            for tb in [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]:
                tool = tools_by_name.get(tb["name"])
                result = tool.execute(**tb.get("input", {})) if tool else {"error": "unknown tool"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb["id"],
                    "content": json.dumps(result),
                })
            conversation.append({"role": "user", "content": tool_results})

        return "Max tool iterations reached."
