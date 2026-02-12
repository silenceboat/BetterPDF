"""
AI Service for DeepRead AI.

Provides chat completion and AI actions using OpenAI API or Ollama.
"""

import os
from typing import Optional


class AIService:
    """
    AI service for chat and document analysis.

    Supports:
    - OpenAI API (GPT-4, GPT-4o-mini, etc.)
    - Ollama (local models)
    """

    def __init__(self, provider: str = "openai", model: Optional[str] = None):
        """
        Initialize the AI service.

        Args:
            provider: "openai" or "ollama"
            model: Model name (defaults to provider-specific default)
        """
        self.provider = provider
        self.model = model or self._get_default_model()
        self.client = None
        self._history: list[dict] = []

        self._init_client()

    def _get_default_model(self) -> str:
        """Get default model for the provider."""
        defaults = {
            "openai": "gpt-4o-mini",
            "ollama": "llama3.2",
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    def _init_client(self):
        """Initialize the API client."""
        if self.provider == "openai":
            try:
                import openai
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.client = openai.OpenAI(api_key=api_key)
            except ImportError:
                pass
        elif self.provider == "ollama":
            # Ollama uses simple HTTP requests
            self.client = "ollama"

    def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        Send a chat message and get a response.

        Args:
            message: User message
            context: Optional context (e.g., selected text from PDF)

        Returns:
            AI response text
        """
        messages = []

        # Add system message
        messages.append({
            "role": "system",
            "content": "You are a helpful AI reading assistant. Help the user understand and analyze documents."
        })

        # Add context if provided
        if context:
            messages.append({
                "role": "user",
                "content": f"Context from document:\n{context}\n\nUser question: {message}"
            })
        else:
            messages.append({"role": "user", "content": message})

        # Call appropriate provider
        if self.provider == "openai" and self.client:
            return self._chat_openai(messages)
        elif self.provider == "ollama":
            return self._chat_ollama(messages)
        else:
            # Fallback mock response
            return self._mock_response(message, context)

    def _chat_openai(self, messages: list[dict]) -> str:
        """Send chat request to OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"

    def _chat_ollama(self, messages: list[dict]) -> str:
        """Send chat request to Ollama."""
        import requests

        try:
            # Convert messages to Ollama format
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            return f"Error connecting to Ollama: {str(e)}\nMake sure Ollama is running on localhost:11434"

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
                f"1. Set your `OPENAI_API_KEY` environment variable for OpenAI, or\n"
                f"2. Install and run [Ollama](https://ollama.com) locally\n\n"
                f"The AI service will automatically detect and use the available provider."
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
