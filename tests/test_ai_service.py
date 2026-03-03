"""Tests for the AI module (providers, ChatSession, AIService)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.ai.providers.base import BaseProvider
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.providers.anthropic import AnthropicProvider
from backend.ai.providers.ollama import OllamaProvider
from backend.ai.chat_session import ChatSession, Message
from backend.ai.service import AIService
from backend.ai.tools import NoteReadTool, NoteWriteTool
from backend.ai.agent import Agent


# ── Helpers ───────────────────────────────────────────────────────────────────

class _DummyProvider(BaseProvider):
    """Minimal concrete provider for testing BaseProvider behaviour."""

    @staticmethod
    def default_model() -> str:
        return "dummy-model"

    @staticmethod
    def env_key() -> str:
        return "DUMMY_API_KEY"

    def chat(self, messages: list[dict], model: str) -> str:
        return "dummy"


# ── Phase 1: Provider validate ────────────────────────────────────────────────

class TestBaseProviderValidate:
    def test_validate_ok_when_api_key_set(self):
        provider = _DummyProvider(api_key="sk-test")
        ok, msg = provider.validate()
        assert ok is True
        assert msg == ""

    def test_validate_fails_when_no_key_and_no_env(self):
        provider = _DummyProvider(api_key="")
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = provider.validate()
        assert ok is False
        assert "DUMMY_API_KEY" in msg

    def test_validate_ok_when_env_key_set(self):
        provider = _DummyProvider(api_key="")
        with patch.dict(os.environ, {"DUMMY_API_KEY": "env-key"}):
            ok, msg = provider.validate()
        assert ok is True
        assert msg == ""

    def test_resolve_api_key_prefers_explicit_key(self):
        provider = _DummyProvider(api_key="explicit")
        with patch.dict(os.environ, {"DUMMY_API_KEY": "env-key"}):
            assert provider.resolve_api_key() == "explicit"

    def test_normalize_base_url_strips_trailing_slash(self):
        provider = _DummyProvider(api_key="k", base_url="https://example.com/")
        assert provider.base_url == "https://example.com"

    def test_normalize_base_url_empty_string(self):
        provider = _DummyProvider(api_key="k", base_url="")
        assert provider.base_url == ""


class TestOpenAIProvider:
    def test_default_model(self):
        assert OpenAIProvider.default_model() == "gpt-4o-mini"

    def test_env_key(self):
        assert OpenAIProvider.env_key() == "OPENAI_API_KEY"

    def test_validate_no_key(self):
        p = OpenAIProvider(api_key="")
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = p.validate()
        assert ok is False

    def test_validate_with_key(self):
        p = OpenAIProvider(api_key="sk-test")
        ok, _ = p.validate()
        assert ok is True


class TestAnthropicProvider:
    def test_default_model(self):
        assert AnthropicProvider.default_model() == "claude-3-5-haiku-latest"

    def test_env_key(self):
        assert AnthropicProvider.env_key() == "ANTHROPIC_API_KEY"

    def test_validate_no_key(self):
        p = AnthropicProvider(api_key="")
        with patch.dict(os.environ, {}, clear=True):
            ok, _ = p.validate()
        assert ok is False

    def test_validate_with_env_key(self):
        p = AnthropicProvider(api_key="")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}):
            ok, _ = p.validate()
        assert ok is True


class TestOllamaProvider:
    def test_default_model(self):
        assert OllamaProvider.default_model() == "llama3.2"

    def test_env_key(self):
        assert OllamaProvider.env_key() == "OLLAMA_API_KEY"

    def test_validate_always_true_without_key(self):
        p = OllamaProvider(api_key="")
        with patch.dict(os.environ, {}, clear=True):
            ok, msg = p.validate()
        assert ok is True
        assert msg == ""

    def test_validate_always_true_with_key(self):
        p = OllamaProvider(api_key="some-key")
        ok, _ = p.validate()
        assert ok is True


# ── Phase 2: ChatSession ──────────────────────────────────────────────────────

class TestChatSession:
    def test_build_messages_contains_system(self):
        session = ChatSession("You are helpful.")
        msgs = session.build_messages("Hello")
        assert msgs[0] == {"role": "system", "content": "You are helpful."}

    def test_build_messages_appends_user(self):
        session = ChatSession("sys")
        msgs = session.build_messages("Hi there")
        assert msgs[-1] == {"role": "user", "content": "Hi there"}

    def test_build_messages_includes_history(self):
        session = ChatSession("sys")
        session.add("user", "first question")
        session.add("assistant", "first answer")
        msgs = session.build_messages("second question")
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user", "assistant", "user"]

    def test_build_messages_truncates_to_max_turns(self):
        session = ChatSession("sys", max_turns=2)
        for i in range(5):
            session.add("user", f"q{i}")
            session.add("assistant", f"a{i}")
        msgs = session.build_messages("new")
        # system + 2*max_turns history + current user = 1 + 4 + 1 = 6
        assert len(msgs) == 6

    def test_clear_empties_history(self):
        session = ChatSession("sys")
        session.add("user", "msg")
        session.clear()
        msgs = session.build_messages("new")
        assert len(msgs) == 2  # only system + current user

    def test_message_dataclass(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


# ── Phase 1+2: AIService registry & delegation ───────────────────────────────

class TestAIServiceRegistry:
    def test_registry_contains_all_providers(self):
        assert "openai" in AIService._PROVIDERS
        assert "anthropic" in AIService._PROVIDERS
        assert "ollama" in AIService._PROVIDERS

    def test_default_model_delegated_to_provider(self):
        svc = AIService(provider="openai")
        assert svc.model == "gpt-4o-mini"

        svc2 = AIService(provider="anthropic")
        assert svc2.model == "claude-3-5-haiku-latest"

        svc3 = AIService(provider="ollama")
        assert svc3.model == "llama3.2"

    def test_unknown_provider_falls_back_to_openai(self):
        svc = AIService(provider="nonexistent")
        assert svc.provider == "openai"

    def test_get_provider_returns_none_without_key(self):
        svc = AIService(provider="openai", api_key="")
        with patch.dict(os.environ, {}, clear=True):
            assert svc._get_provider() is None

    def test_get_provider_returns_none_for_anthropic_without_key(self):
        svc = AIService(provider="anthropic", api_key="")
        with patch.dict(os.environ, {}, clear=True):
            assert svc._get_provider() is None

    def test_get_provider_returns_instance_for_ollama_without_key(self):
        svc = AIService(provider="ollama", api_key="")
        provider = svc._get_provider()
        assert isinstance(provider, OllamaProvider)

    def test_resolve_api_key_uses_env(self):
        svc = AIService(provider="openai", api_key="")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "from-env"}):
            assert svc._resolve_api_key() == "from-env"

    def test_resolve_api_key_prefers_explicit(self):
        svc = AIService(provider="openai", api_key="explicit")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "from-env"}):
            assert svc._resolve_api_key() == "explicit"


class TestAIServiceChat:
    def test_chat_returns_mock_when_no_provider(self):
        svc = AIService(provider="openai", api_key="")
        with patch.dict(os.environ, {}, clear=True):
            response = svc.chat("Hello")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_chat_with_context_returns_mock(self):
        svc = AIService(provider="openai", api_key="")
        with patch.dict(os.environ, {}, clear=True):
            response = svc.chat("What is this?", context="Some document text")
        assert "Analysis" in response or "mock" in response.lower()

    def test_chat_calls_provider_when_available(self):
        svc = AIService(provider="ollama", api_key="")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            response = svc.chat("Hello")
        assert response == "dummy"

    def test_chat_accumulates_session_history(self):
        svc = AIService(provider="ollama", api_key="")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            svc.chat("First")
            svc.chat("Second")
        msgs = svc._session.build_messages("Third")
        # system + user/assistant * 2 turns + current user = 1 + 4 + 1 = 6
        assert len(msgs) == 6


class TestAIServiceConfigure:
    def test_configure_clears_session(self):
        svc = AIService(provider="ollama", api_key="")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            svc.chat("Hello")
        # session has history now
        assert len(svc._session._history) == 2

        svc.configure(provider="ollama")
        assert len(svc._session._history) == 0

    def test_configure_switches_provider(self):
        svc = AIService(provider="openai")
        svc.configure(provider="anthropic")
        assert svc.provider == "anthropic"

    def test_configure_updates_default_model_when_model_cleared(self):
        svc = AIService(provider="openai")
        svc.configure(provider="anthropic", model="")
        assert svc.model == "claude-3-5-haiku-latest"

    def test_configure_keeps_explicit_model(self):
        svc = AIService(provider="openai")
        svc.configure(model="gpt-4o")
        assert svc.model == "gpt-4o"

    def test_clear_history_delegates_to_session(self):
        svc = AIService(provider="ollama")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            svc.chat("msg")
        svc.clear_history()
        assert len(svc._session._history) == 0


# ── Phase 3: Tools ────────────────────────────────────────────────────────────

class TestTools:
    def test_note_read_tool_returns_content(self):
        tool = NoteReadTool(get_note_fn=lambda: "my note")
        result = tool.execute()
        assert result == {"content": "my note"}

    def test_note_read_tool_handles_none(self):
        tool = NoteReadTool(get_note_fn=lambda: None)
        result = tool.execute()
        assert result == {"content": ""}

    def test_note_write_tool_calls_save(self):
        saved: list[str] = []
        tool = NoteWriteTool(save_note_fn=lambda c: saved.append(c))
        result = tool.execute(content="updated note")
        assert result == {"success": True}
        assert saved == ["updated note"]

    def test_note_read_tool_name(self):
        tool = NoteReadTool(get_note_fn=lambda: "")
        assert tool.name == "note_read"

    def test_note_write_tool_name(self):
        tool = NoteWriteTool(save_note_fn=lambda c: None)
        assert tool.name == "note_write"


# ── Phase 3: Agent ────────────────────────────────────────────────────────────

class TestAgent:
    def test_agent_run_delegates_to_provider(self):
        agent = Agent(name="test", system_prompt="Be helpful")
        provider = _DummyProvider(api_key="")
        result = agent.run("Hello", provider, "dummy-model")
        assert result == "dummy"

    def test_agent_registers_tools(self):
        tool = NoteReadTool(get_note_fn=lambda: "note")
        agent = Agent(name="test", system_prompt="sys", tools=[tool])
        assert "note_read" in agent.tools

    def test_agent_no_tools_by_default(self):
        agent = Agent(name="test", system_prompt="sys")
        assert agent.tools == {}
