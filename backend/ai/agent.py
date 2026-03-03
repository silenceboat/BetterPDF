"""Agent base class and concrete agent implementations."""

from __future__ import annotations

from .chat_session import ChatSession
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
        """Single-turn execution with optional tool calling."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        tools = list(self.tools.values())
        if tools and provider.supports_tools():
            return provider.chat_with_tools(messages, model, tools)
        return provider.chat(messages, model)


class ChatAgent(Agent):
    """Multi-turn chat agent with persistent session history and tool support."""

    def __init__(
        self,
        system_prompt: str,
        tools: list[Tool] | None = None,
        max_turns: int = 10,
    ) -> None:
        super().__init__("chat", system_prompt, tools)
        self._session = ChatSession(system_prompt, max_turns)

    def chat(
        self,
        message: str,
        context: str | None,
        provider: BaseProvider,
        model: str,
    ) -> str:
        user_content = (
            f"Document context:\n{context}\n\nUser: {message}" if context else message
        )
        messages = self._session.build_messages(user_content)
        agent_tools = list(self.tools.values())
        if agent_tools and provider.supports_tools():
            response = provider.chat_with_tools(messages, model, agent_tools)
        else:
            response = provider.chat(messages, model)
        self._session.add("user", user_content)
        self._session.add("assistant", response)
        return response

    def clear_history(self) -> None:
        self._session.clear()


class NoteAssistAgent(Agent):
    """Single-turn agent for note assistance with optional tool support."""

    def __init__(
        self,
        system_prompt: str,
        tools: list[Tool] | None = None,
    ) -> None:
        super().__init__("note_assist", system_prompt, tools)


class DocumentAgent(Agent):
    """Single-turn agent for document analysis with optional tool support."""

    def __init__(
        self,
        system_prompt: str,
        tools: list[Tool] | None = None,
    ) -> None:
        super().__init__("document", system_prompt, tools)
