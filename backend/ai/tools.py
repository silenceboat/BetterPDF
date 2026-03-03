"""Tool abstraction and built-in note/document tools."""

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

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def execute(self, **params) -> dict: ...

    def to_openai_spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class NoteReadTool(Tool):
    name = "note_read"
    description = "List notes for the current document, optionally filtered by page"

    def __init__(self, list_notes_fn: Callable[..., list[dict]]) -> None:
        self._list_notes = list_notes_fn

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Optional page number to filter notes",
                },
            },
            "required": [],
        }

    def execute(self, page: int | None = None, **params) -> dict:
        notes = self._list_notes(page=page) or []
        return {"notes": notes}


class NoteWriteTool(Tool):
    name = "note_write"
    description = "Write or update the current note content"

    def __init__(self, save_note_fn: Callable[[str], None]) -> None:
        self._save_note = save_note_fn

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The note content to write",
                },
            },
            "required": ["content"],
        }

    def execute(self, content: str = "", **params) -> dict:
        self._save_note(content)
        return {"success": True}


class NoteDeleteTool(Tool):
    name = "note_delete"
    description = "Delete a note by its ID"

    def __init__(self, delete_note_fn: Callable[[str], None]) -> None:
        self._delete_note = delete_note_fn

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "string",
                    "description": "The ID of the note to delete",
                },
            },
            "required": ["note_id"],
        }

    def execute(self, note_id: str = "", **params) -> dict:
        self._delete_note(note_id)
        return {"success": True}


class DocumentSearchTool(Tool):
    name = "document_search"
    description = "Search for text in the current document"

    def __init__(self, search_fn: Callable[..., list[dict]]) -> None:
        self._search = search_fn

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "page": {
                    "type": "integer",
                    "description": "Optional page number to search within",
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str = "", page: int | None = None, **params) -> dict:
        results = self._search(query, page) or []
        return {"results": results}
