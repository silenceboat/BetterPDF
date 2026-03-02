"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], model: str) -> str: ...
