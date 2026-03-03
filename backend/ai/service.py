"""AIService — routes messages to the appropriate provider."""

from __future__ import annotations

from typing import Any, Optional

from .chat_session import ChatSession
from .prompts import SYSTEM_PROMPT, AI_ACTIONS, QUICK_ACTIONS, NOTE_ASSIST_ACTIONS
from .providers import OpenAIProvider, AnthropicProvider, OllamaProvider, BaseProvider


class AIService:
    """AI service for chat and document analysis."""

    _PROVIDERS: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = self._normalize_provider(provider)
        self.api_key = str(api_key or "").strip()
        self.base_url = BaseProvider._normalize_base_url(base_url or "")
        self.model = model or self._get_default_model()
        self._session = ChatSession(SYSTEM_PROMPT)

    # ── Normalization ──────────────────────────────────────────────────────────

    def _get_default_model(self) -> str:
        cls = self._PROVIDERS.get(self.provider)
        return cls.default_model() if cls else "gpt-4o-mini"

    @classmethod
    def _normalize_provider(cls, provider: Optional[str]) -> str:
        candidate = str(provider or "").strip().lower()
        return candidate if candidate in cls._PROVIDERS else "openai"

    def _resolve_api_key(self) -> str:
        cls = self._PROVIDERS.get(self.provider)
        if cls is None:
            return self.api_key
        tmp = cls(api_key=self.api_key)
        return tmp.resolve_api_key()

    # ── Configuration ──────────────────────────────────────────────────────────

    def configure(
        self,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Update runtime AI configuration and clear history."""
        if provider is not None:
            self.provider = self._normalize_provider(provider)
        if model is not None:
            self.model = str(model or "").strip() or self._get_default_model()
        if base_url is not None:
            self.base_url = BaseProvider._normalize_base_url(base_url)
        if api_key is not None:
            self.api_key = str(api_key or "").strip()
        self._session.clear()

    def get_config(self) -> dict[str, Any]:
        resolved_key = self._resolve_api_key()
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "has_api_key": bool(resolved_key),
        }

    # ── Provider factory ───────────────────────────────────────────────────────

    def _get_provider(self) -> Optional[BaseProvider]:
        """Return an initialized provider or None if unavailable."""
        cls = self._PROVIDERS.get(self.provider)
        if cls is None:
            return None
        resolved_key = self._resolve_api_key()
        instance = cls(api_key=resolved_key, base_url=self.base_url)
        ok, _ = instance.validate()
        return instance if ok else None

    # ── Chat ───────────────────────────────────────────────────────────────────

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """Send a chat message and return the AI response."""
        if context:
            user_content = f"Context from document:\n{context}\n\nUser question: {message}"
        else:
            user_content = message

        messages = self._session.build_messages(user_content)

        provider = self._get_provider()
        if provider is None:
            return self._mock_response(message, context)

        response = provider.chat(messages, self.model)
        self._session.add("user", user_content)
        self._session.add("assistant", response)
        return response

    # ── AI actions ─────────────────────────────────────────────────────────────

    def ai_action(self, action: str, selected_text: str) -> str:
        template = AI_ACTIONS.get(action, "Process this text:\n\n{text}")
        prompt = template.format(text=selected_text)
        return self.chat(prompt)

    def quick_action(self, action_type: str, document_context: str = "") -> str:
        prompt = QUICK_ACTIONS.get(action_type, "Analyze this document.")
        if document_context:
            prompt += f"\n\nDocument context:\n{document_context}"
        return self.chat(prompt)

    def note_assist(self, note_content: str, quote: str, action: str, instruction: str = "") -> str:
        """Apply an AI action to a note, returning the improved text."""
        if action == "custom":
            parts = [instruction.strip() or "Improve this note."]
            if note_content:
                parts.append(f"\nNote:\n{note_content}")
            if quote:
                parts.append(f"\nContext (quoted from document):\n{quote}")
            return self.chat("\n".join(parts))
        template = NOTE_ASSIST_ACTIONS.get(action)
        if template is None:
            raise ValueError(f"Unknown note assist action: {action!r}")
        prompt = template.format(note=note_content, quote=quote)
        return self.chat(prompt)

    # ── History ────────────────────────────────────────────────────────────────

    def clear_history(self) -> None:
        self._session.clear()

    # ── Mock fallback ──────────────────────────────────────────────────────────

    def _mock_response(self, message: str, context: Optional[str]) -> str:
        if context:
            return (
                "**Analysis of Selected Text**\n\n"
                "I've analyzed the text you selected. Here's what I found:\n\n"
                "- **Key Point**: The selected text discusses important concepts related to your query.\n"
                "- **Context**: This appears to be from an academic or technical document.\n"
                "- **Recommendation**: Consider reviewing related sections for more context.\n\n"
                "*Note: This is a mock response. Configure OpenAI API key or Ollama for real AI responses.*"
            )
        return (
            f'**Response to: "{message[:50]}..."**\n\n'
            "This is a mock response. To get real AI responses, please:\n\n"
            "1. Set Provider URL and API Key in AI settings, or\n"
            "2. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` environment variable, or\n"
            "3. Install and run [Ollama](https://ollama.com) locally\n\n"
            "The app supports OpenAI-compatible URLs, Anthropic, and Ollama."
        )
