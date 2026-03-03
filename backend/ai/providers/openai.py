"""OpenAI / OpenAI-compatible provider."""

from __future__ import annotations

import json
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

    def supports_tools(self) -> bool:
        return True

    def chat_with_tools(
        self,
        messages: list[dict],
        model: str,
        tools: list,
        max_iterations: int = 5,
    ) -> str:
        self._ensure_client()
        if not self._client:
            raise RuntimeError("OpenAI client not available. Check api_key and openai package.")
        tool_specs = [t.to_openai_spec() for t in tools]
        tools_by_name = {t.name: t for t in tools}
        msgs = list(messages)

        for _ in range(max_iterations):
            resp = self._client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=tool_specs,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2000,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            msgs.append(msg.model_dump(exclude_unset=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                tool = tools_by_name.get(tc.function.name)
                result = tool.execute(**args) if tool else {"error": "unknown tool"}
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        return "Max tool iterations reached."
