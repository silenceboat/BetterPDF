"""Chat session — manages conversation history for a single AI session."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


class ChatSession:
    def __init__(self, system_prompt: str, max_turns: int = 10) -> None:
        self._system = Message(role="system", content=system_prompt)
        self._history: list[Message] = []
        self._max_turns = max_turns

    def add(self, role: str, content: str) -> None:
        self._history.append(Message(role=role, content=content))

    def build_messages(self, user_content: str) -> list[dict]:
        """Assemble a complete messages list for provider.chat()."""
        recent = self._history[-(self._max_turns * 2):]
        return (
            [{"role": "system", "content": self._system.content}]
            + [{"role": m.role, "content": m.content} for m in recent]
            + [{"role": "user", "content": user_content}]
        )

    def clear(self) -> None:
        self._history.clear()
