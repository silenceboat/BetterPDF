"""AIService — routes messages to the appropriate provider."""

from __future__ import annotations

from typing import Any, Optional

from .agent import ChatAgent, NoteAssistAgent, DocumentAgent
from .prompts import (
    SYSTEM_PROMPT,
    NOTE_ASSIST_SYSTEM_PROMPT,
    DOCUMENT_SYSTEM_PROMPT,
    AI_ACTIONS,
    QUICK_ACTIONS,
    NOTE_ASSIST_ACTIONS,
)
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
        # Agents (created with no tools; call configure_agents() to inject tools)
        self._chat_agent = ChatAgent(SYSTEM_PROMPT)
        self._note_agent = NoteAssistAgent(NOTE_ASSIST_SYSTEM_PROMPT)
        self._doc_agent = DocumentAgent(DOCUMENT_SYSTEM_PROMPT)

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
        """Update runtime AI configuration and clear chat history."""
        if provider is not None:
            self.provider = self._normalize_provider(provider)
        if model is not None:
            self.model = str(model or "").strip() or self._get_default_model()
        if base_url is not None:
            self.base_url = BaseProvider._normalize_base_url(base_url)
        if api_key is not None:
            self.api_key = str(api_key or "").strip()
        self._chat_agent.clear_history()

    def configure_agents(
        self,
        *,
        chat_tools: Optional[list] = None,
        note_assist_tools: Optional[list] = None,
        document_tools: Optional[list] = None,
    ) -> None:
        """Inject tools into agents. Replaces agents with new instances."""
        if chat_tools is not None:
            self._chat_agent = ChatAgent(SYSTEM_PROMPT, chat_tools)
        if note_assist_tools is not None:
            self._note_agent = NoteAssistAgent(NOTE_ASSIST_SYSTEM_PROMPT, note_assist_tools)
        if document_tools is not None:
            self._doc_agent = DocumentAgent(DOCUMENT_SYSTEM_PROMPT, document_tools)

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
        provider = self._get_provider()
        if provider is None:
            return self._mock_response(message, context)
        return self._chat_agent.chat(message, context, provider, self.model)

    # ── AI actions ─────────────────────────────────────────────────────────────

    def ai_action(self, action: str, selected_text: str) -> str:
        template = AI_ACTIONS.get(action, "Process this text:\n\n{text}")
        prompt = template.format(text=selected_text)
        provider = self._get_provider()
        if provider is None:
            return self._mock_response(selected_text, None)
        return self._doc_agent.run(prompt, provider, self.model)

    def quick_action(self, action_type: str, document_context: str = "") -> str:
        prompt = QUICK_ACTIONS.get(action_type, "Analyze this document.")
        if document_context:
            prompt += f"\n\nDocument context:\n{document_context}"
        provider = self._get_provider()
        if provider is None:
            return self._mock_response(action_type, document_context or None)
        return self._doc_agent.run(prompt, provider, self.model)

    def note_assist(self, note_content: str, quote: str, action: str, instruction: str = "") -> str:
        """Apply an AI action to a note, returning the improved text."""
        if action == "custom":
            parts = [instruction.strip() or "Improve this note."]
            if note_content:
                parts.append(f"\nNote:\n{note_content}")
            if quote:
                parts.append(f"\nContext (quoted from document):\n{quote}")
            prompt = "\n".join(parts)
        else:
            template = NOTE_ASSIST_ACTIONS.get(action)
            if template is None:
                raise ValueError(f"Unknown note assist action: {action!r}")
            prompt = template.format(note=note_content, quote=quote)
        provider = self._get_provider()
        if provider is None:
            return self._mock_response(note_content or action, None)
        return self._note_agent.run(prompt, provider, self.model)

    # ── History ────────────────────────────────────────────────────────────────

    def clear_history(self) -> None:
        self._chat_agent.clear_history()

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
