"""Tool abstraction and built-in note tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def execute(self, **params) -> dict: ...


class NoteReadTool(Tool):
    name = "note_read"
    description = "Read the content of the current note"

    def __init__(self, get_note_fn: Callable[[], str | None]) -> None:
        self._get_note = get_note_fn

    def execute(self, **params) -> dict:
        return {"content": self._get_note() or ""}


class NoteWriteTool(Tool):
    name = "note_write"
    description = "Write or update the current note content"

    def __init__(self, save_note_fn: Callable[[str], None]) -> None:
        self._save_note = save_note_fn

    def execute(self, content: str = "", **params) -> dict:
        self._save_note(content)
        return {"success": True}
