"""Agent base class — holds tools and delegates to a provider."""

from __future__ import annotations

from .providers.base import BaseProvider
from .tools import Tool


class Agent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[Tool] | None = None,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}

    def run(self, user_input: str, provider: BaseProvider, model: str) -> str:
        """Single-turn execution: send message to AI and return response."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        return provider.chat(messages, model)
