"""AI service with configurable provider endpoint and credentials."""

from __future__ import annotations

import os
from typing import Any, Optional


class AIService:
    """AI service for chat and document analysis."""

    _VALID_PROVIDERS = {"openai", "anthropic", "ollama"}

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = self._normalize_provider(provider)
        self.model = model or self._get_default_model()
        self.base_url = self._normalize_base_url(base_url)
        self.api_key = str(api_key or "").strip()
        self.client = None
        self._history: list[dict] = []
        self._init_client()

    def _get_default_model(self) -> str:
        """Get default model for the provider."""
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-latest",
            "ollama": "llama3.2",
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    @classmethod
    def _normalize_provider(cls, provider: Optional[str]) -> str:
        candidate = str(provider or "").strip().lower()
        return candidate if candidate in cls._VALID_PROVIDERS else "openai"

    @staticmethod
    def _normalize_base_url(base_url: Optional[str]) -> str:
        return str(base_url or "").strip().rstrip("/")

    def _get_provider_env_key(self) -> str:
        if self.provider == "anthropic":
            return "ANTHROPIC_API_KEY"
        if self.provider == "openai":
            return "OPENAI_API_KEY"
        return "OLLAMA_API_KEY"

    def _resolve_api_key(self) -> str:
        env_key = self._get_provider_env_key()
        return self.api_key or os.getenv(env_key, "")

    def _init_client(self):
        """Mark client for lazy re-initialization."""
        self._client_initialized = False
        self.client = None

    def configure(
        self,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Update runtime AI configuration and reset lazy client."""
        if provider is not None:
            self.provider = self._normalize_provider(provider)
        if model is not None:
            self.model = str(model or "").strip() or self._get_default_model()
        if base_url is not None:
            self.base_url = self._normalize_base_url(base_url)
        if api_key is not None:
            self.api_key = str(api_key or "").strip()
        self._init_client()
        self._history.clear()

    def get_config(self) -> dict[str, Any]:
        """Return active AI settings (includes key for local UI persistence)."""
        resolved_key = self._resolve_api_key()
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "has_api_key": bool(resolved_key),
        }

    def _ensure_client(self):
        """Ensure the API client is initialized (lazy)."""
        if self._client_initialized:
            return
        self._client_initialized = True

        if self.provider == "openai":
            try:
                import openai
                api_key = self._resolve_api_key()
                if api_key:
                    kwargs: dict[str, Any] = {"api_key": api_key}
                    if self.base_url:
                        kwargs["base_url"] = self.base_url
                    self.client = openai.OpenAI(**kwargs)
            except ImportError:
                pass
        elif self.provider == "anthropic":
            if self._resolve_api_key():
                self.client = "anthropic"
        elif self.provider == "ollama":
            self.client = "ollama"

    _MAX_HISTORY_TURNS = 10  # keep last N user/assistant pairs

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        Send a chat message and get a response.

        Args:
            message: User message
            context: Optional context (e.g., selected text from PDF)

        Returns:
            AI response text
        """
        system_msg = {
            "role": "system",
            "content": "You are a helpful AI reading assistant. Help the user understand and analyze documents."
        }

        # Build the user turn (with optional document context)
        if context:
            user_content = f"Context from document:\n{context}\n\nUser question: {message}"
        else:
            user_content = message

        user_msg = {"role": "user", "content": user_content}

        # Assemble full messages: system + trimmed history + current user turn
        messages = [system_msg] + self._history[-self._MAX_HISTORY_TURNS * 2:] + [user_msg]

        # Call appropriate provider
        self._ensure_client()
        if self.provider == "openai" and self.client:
            response = self._chat_openai(messages)
        elif self.provider == "anthropic" and self.client:
            response = self._chat_anthropic(messages)
        elif self.provider == "ollama":
            response = self._chat_ollama(messages)
        else:
            # Fallback mock response
            return self._mock_response(message, context)

        # Persist to history only on success
        self._history.append(user_msg)
        self._history.append({"role": "assistant", "content": response})

        return response

    def _chat_openai(self, messages: list[dict]) -> str:
        """Send chat request to OpenAI."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    def _chat_ollama(self, messages: list[dict]) -> str:
        """Send chat request to Ollama using /api/chat."""
        import requests

        base_url = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        endpoint = base_url.rstrip("/") + "/api/chat"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            endpoint,
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
            },
            headers=headers or None,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def _chat_anthropic(self, messages: list[dict]) -> str:
        """Send chat request to Anthropic Messages API."""
        import requests

        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError("Anthropic API key is missing. Set it in Settings or ANTHROPIC_API_KEY.")

        base_url = self.base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        endpoint = base_url.rstrip("/") + "/v1/messages"

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
            "model": self.model,
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
                "x-api-key": api_key,
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

    def _mock_response(self, message: str, context: Optional[str]) -> str:
        """Generate a mock response when no AI provider is available."""
        if context:
            return (
                f"**Analysis of Selected Text**\n\n"
                f"I've analyzed the text you selected. Here's what I found:\n\n"
                f"- **Key Point**: The selected text discusses important concepts related to your query.\n"
                f"- **Context**: This appears to be from an academic or technical document.\n"
                f"- **Recommendation**: Consider reviewing related sections for more context.\n\n"
                f"*Note: This is a mock response. Configure OpenAI API key or Ollama for real AI responses.*"
            )
        else:
            return (
                f"**Response to: \"{message[:50]}...\"**\n\n"
                f"This is a mock response. To get real AI responses, please:\n\n"
                f"1. Set Provider URL and API Key in AI settings, or\n"
                f"2. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` environment variable, or\n"
                f"3. Install and run [Ollama](https://ollama.com) locally\n\n"
                f"The app supports OpenAI-compatible URLs, Anthropic, and Ollama."
            )

    def ai_action(self, action: str, selected_text: str) -> str:
        """
        Perform an AI action on selected text.

        Args:
            action: Action type (explain, summarize, translate, define)
            selected_text: Text to process

        Returns:
            AI response
        """
        actions = {
            "explain": f"Explain the following text in detail:\n\n{selected_text}",
            "summarize": f"Summarize the following text concisely:\n\n{selected_text}",
            "translate": f"Translate the following text to Chinese:\n\n{selected_text}",
            "define": f"Define or explain the key terms in:\n\n{selected_text}",
            "ask": f"Answer the following about this text:\n\n{selected_text}",
        }

        prompt = actions.get(action, f"Process this text:\n\n{selected_text}")
        return self.chat(prompt)

    def quick_action(self, action_type: str, document_context: str = "") -> str:
        """
        Perform a quick action on the entire document.

        Args:
            action_type: Type of quick action (full_summary, key_points, questions)
            document_context: Context about the document

        Returns:
            AI response
        """
        prompts = {
            "full_summary": "Provide a comprehensive summary of this document.",
            "key_points": "Extract the key points and main arguments from this document.",
            "questions": "Generate thought-provoking questions based on this document.",
        }

        prompt = prompts.get(action_type, "Analyze this document.")

        if document_context:
            prompt += f"\n\nDocument context:\n{document_context}"

        return self.chat(prompt)

    def clear_history(self):
        """Clear the conversation history."""
        self._history.clear()
