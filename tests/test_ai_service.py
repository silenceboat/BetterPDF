"""Tests for the AI module (providers, ChatSession, AIService, tools, agents)."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from backend.ai.providers.base import BaseProvider
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.providers.anthropic import AnthropicProvider
from backend.ai.providers.ollama import OllamaProvider
from backend.ai.chat_session import ChatSession, Message
from backend.ai.service import AIService
from backend.ai.tools import NoteReadTool, NoteWriteTool, NoteDeleteTool, DocumentSearchTool
from backend.ai.agent import Agent, ChatAgent, NoteAssistAgent, DocumentAgent


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


class _ToolProvider(_DummyProvider):
    """Provider that advertises tool support and records calls."""

    def __init__(self, tool_response: str = "tool-result"):
        super().__init__(api_key="key")
        self._tool_response = tool_response
        self.chat_with_tools_calls: list = []

    def supports_tools(self) -> bool:
        return True

    def chat_with_tools(self, messages, model, tools, max_iterations=5) -> str:
        self.chat_with_tools_calls.append((messages, model, tools))
        return self._tool_response


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

    def test_supports_tools_default_false(self):
        provider = _DummyProvider(api_key="k")
        assert provider.supports_tools() is False

    def test_chat_with_tools_fallback_to_chat(self):
        provider = _DummyProvider(api_key="k")
        msgs = [{"role": "user", "content": "hi"}]
        result = provider.chat_with_tools(msgs, "m", [])
        assert result == "dummy"


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

    def test_supports_tools_true(self):
        assert OpenAIProvider(api_key="k").supports_tools() is True


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

    def test_supports_tools_true(self):
        assert AnthropicProvider(api_key="k").supports_tools() is True


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
        msgs = svc._chat_agent._session.build_messages("Third")
        # system + user/assistant * 2 turns + current user = 1 + 4 + 1 = 6
        assert len(msgs) == 6


class TestAIServiceConfigure:
    def test_configure_clears_session(self):
        svc = AIService(provider="ollama", api_key="")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            svc.chat("Hello")
        assert len(svc._chat_agent._session._history) == 2

        svc.configure(provider="ollama")
        assert len(svc._chat_agent._session._history) == 0

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
        assert len(svc._chat_agent._session._history) == 0


# ── Phase 3: Tool specs ───────────────────────────────────────────────────────

class TestToolSpecs:
    def test_to_openai_spec_format(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        spec = tool.to_openai_spec()
        assert spec["type"] == "function"
        fn = spec["function"]
        assert fn["name"] == "note_read"
        assert "description" in fn
        assert fn["parameters"]["type"] == "object"

    def test_to_anthropic_spec_format(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        spec = tool.to_anthropic_spec()
        assert spec["name"] == "note_read"
        assert "description" in spec
        assert "input_schema" in spec
        assert spec["input_schema"]["type"] == "object"

    def test_document_search_tool_openai_spec(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        spec = tool.to_openai_spec()
        params = spec["function"]["parameters"]
        assert "query" in params["properties"]
        assert "query" in params["required"]

    def test_note_delete_tool_anthropic_spec(self):
        tool = NoteDeleteTool(delete_note_fn=lambda note_id: None)
        spec = tool.to_anthropic_spec()
        assert spec["name"] == "note_delete"
        assert "note_id" in spec["input_schema"]["properties"]
        assert "note_id" in spec["input_schema"]["required"]

    def test_note_write_tool_parameters(self):
        tool = NoteWriteTool(save_note_fn=lambda c: None)
        params = tool.parameters
        assert "content" in params["properties"]
        assert "content" in params["required"]


# ── Phase 3: Tools ────────────────────────────────────────────────────────────

class TestNoteReadTool:
    def test_returns_notes_list(self):
        notes = [{"id": "1", "content": "note one"}]
        tool = NoteReadTool(list_notes_fn=lambda page=None: notes)
        result = tool.execute()
        assert result == {"notes": notes}

    def test_returns_empty_when_no_notes(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        result = tool.execute()
        assert result == {"notes": []}

    def test_passes_page_to_fn(self):
        received: list = []
        tool = NoteReadTool(list_notes_fn=lambda page=None: received.append(page) or [])
        tool.execute(page=3)
        assert received == [3]

    def test_name(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        assert tool.name == "note_read"


class TestNoteWriteTool:
    def test_calls_save_and_returns_success(self):
        saved: list[str] = []
        tool = NoteWriteTool(save_note_fn=lambda c: saved.append(c))
        result = tool.execute(content="updated note")
        assert result == {"success": True}
        assert saved == ["updated note"]

    def test_name(self):
        tool = NoteWriteTool(save_note_fn=lambda c: None)
        assert tool.name == "note_write"


class TestNoteDeleteTool:
    def test_calls_delete_fn_and_returns_success(self):
        deleted: list[str] = []
        tool = NoteDeleteTool(delete_note_fn=lambda nid: deleted.append(nid))
        result = tool.execute(note_id="abc123")
        assert result == {"success": True}
        assert deleted == ["abc123"]

    def test_name(self):
        tool = NoteDeleteTool(delete_note_fn=lambda nid: None)
        assert tool.name == "note_delete"


class TestDocumentSearchTool:
    def test_returns_results(self):
        results = [{"page": 1, "text": "found"}]
        tool = DocumentSearchTool(search_fn=lambda q, page=None: results)
        result = tool.execute(query="test")
        assert result == {"results": results}

    def test_passes_query_and_page(self):
        received: list = []
        tool = DocumentSearchTool(search_fn=lambda q, page=None: received.append((q, page)) or [])
        tool.execute(query="hello", page=2)
        assert received == [("hello", 2)]

    def test_returns_empty_on_no_match(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        result = tool.execute(query="xyz")
        assert result == {"results": []}

    def test_name(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        assert tool.name == "document_search"


# ── Phase 3: BaseProvider tool fallback ──────────────────────────────────────

class TestBaseProviderToolFallback:
    def test_chat_with_tools_falls_back_to_chat(self):
        provider = _DummyProvider(api_key="k")
        msgs = [{"role": "user", "content": "hi"}]
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        result = provider.chat_with_tools(msgs, "dummy-model", [tool])
        assert result == "dummy"

    def test_supports_tools_is_false(self):
        assert _DummyProvider(api_key="k").supports_tools() is False


# ── Phase 3: OpenAI provider with tools ──────────────────────────────────────

class TestOpenAIProviderWithTools:
    def _make_tool(self):
        called: list = []

        class _EchoTool:
            name = "echo"
            description = "echo"

            def to_openai_spec(self):
                return {"type": "function", "function": {
                    "name": "echo", "description": "echo",
                    "parameters": {"type": "object", "properties": {
                        "msg": {"type": "string"}}, "required": ["msg"]}}}

            def execute(self, msg="", **kw):
                called.append(msg)
                return {"echoed": msg}

        return _EchoTool(), called

    def test_single_tool_call_then_final_response(self):
        tool, called = self._make_tool()

        # First response: requests tool call
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "echo"
        tc.function.arguments = json.dumps({"msg": "hello"})

        msg1 = MagicMock()
        msg1.tool_calls = [tc]
        msg1.content = None
        msg1.model_dump.return_value = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_001",
                "type": "function",
                "function": {"name": "echo", "arguments": '{"msg": "hello"}'},
            }],
        }

        # Second response: final text
        msg2 = MagicMock()
        msg2.tool_calls = None
        msg2.content = "Done: hello"

        resp1 = MagicMock()
        resp1.choices = [MagicMock(message=msg1)]
        resp2 = MagicMock()
        resp2.choices = [MagicMock(message=msg2)]

        provider = OpenAIProvider(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        provider._client = mock_client
        provider._initialized = True

        messages = [{"role": "user", "content": "test"}]
        result = provider.chat_with_tools(messages, "gpt-4o", [tool])

        assert result == "Done: hello"
        assert called == ["hello"]
        assert mock_client.chat.completions.create.call_count == 2

    def test_no_tool_calls_returns_content_directly(self):
        msg = MagicMock()
        msg.tool_calls = None
        msg.content = "Direct answer"

        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]

        provider = OpenAIProvider(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = resp
        provider._client = mock_client
        provider._initialized = True

        tool, _ = self._make_tool()
        result = provider.chat_with_tools([{"role": "user", "content": "hi"}], "gpt-4o", [tool])
        assert result == "Direct answer"


# ── Phase 3: Anthropic provider with tools ───────────────────────────────────

class TestAnthropicProviderWithTools:
    def _make_tool(self):
        called: list = []

        class _SearchTool:
            name = "search"
            description = "search"

            def to_anthropic_spec(self):
                return {"name": "search", "description": "search",
                        "input_schema": {"type": "object",
                                         "properties": {"q": {"type": "string"}},
                                         "required": ["q"]}}

            def execute(self, q="", **kw):
                called.append(q)
                return {"results": [q]}

        return _SearchTool(), called

    def test_tool_use_then_final_text(self):
        tool, called = self._make_tool()

        # First response: tool_use
        resp1_data = {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "id": "tu_001", "name": "search", "input": {"q": "foo"}},
            ],
        }
        # Second response: text
        resp2_data = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "Found: foo"}],
        }

        mock_resp1 = MagicMock()
        mock_resp1.raise_for_status = MagicMock()
        mock_resp1.json.return_value = resp1_data

        mock_resp2 = MagicMock()
        mock_resp2.raise_for_status = MagicMock()
        mock_resp2.json.return_value = resp2_data

        provider = AnthropicProvider(api_key="sk-ant")
        messages = [{"role": "user", "content": "find foo"}]

        with patch("requests.post", side_effect=[mock_resp1, mock_resp2]):
            result = provider.chat_with_tools(messages, "claude-3-5-haiku-latest", [tool])

        assert result == "Found: foo"
        assert called == ["foo"]

    def test_no_tool_use_returns_text_directly(self):
        resp_data = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "Direct answer"}],
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = resp_data

        tool, _ = self._make_tool()
        provider = AnthropicProvider(api_key="sk-ant")
        messages = [{"role": "user", "content": "hi"}]

        with patch("requests.post", return_value=mock_resp):
            result = provider.chat_with_tools(messages, "claude-3-5-haiku-latest", [tool])

        assert result == "Direct answer"


# ── Phase 3: Agent ────────────────────────────────────────────────────────────

class TestAgent:
    def test_agent_run_delegates_to_provider(self):
        agent = Agent(name="test", system_prompt="Be helpful")
        provider = _DummyProvider(api_key="")
        result = agent.run("Hello", provider, "dummy-model")
        assert result == "dummy"

    def test_agent_registers_tools(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        agent = Agent(name="test", system_prompt="sys", tools=[tool])
        assert "note_read" in agent.tools

    def test_agent_no_tools_by_default(self):
        agent = Agent(name="test", system_prompt="sys")
        assert agent.tools == {}

    def test_agent_run_uses_chat_with_tools_when_provider_supports(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        agent = Agent(name="test", system_prompt="sys", tools=[tool])
        provider = _ToolProvider(tool_response="from-tools")
        result = agent.run("Hello", provider, "m")
        assert result == "from-tools"
        assert len(provider.chat_with_tools_calls) == 1

    def test_agent_run_uses_chat_when_no_tools(self):
        agent = Agent(name="test", system_prompt="sys")
        provider = _ToolProvider()
        result = agent.run("Hello", provider, "m")
        assert result == "dummy"
        assert len(provider.chat_with_tools_calls) == 0


# ── Phase 3: ChatAgent ────────────────────────────────────────────────────────

class TestChatAgent:
    def test_chat_accumulates_history(self):
        agent = ChatAgent(system_prompt="sys")
        provider = _DummyProvider(api_key="")
        agent.chat("First", None, provider, "m")
        agent.chat("Second", None, provider, "m")
        msgs = agent._session.build_messages("Third")
        # system + 2 turns (user+assistant each) + current user = 1 + 4 + 1 = 6
        assert len(msgs) == 6

    def test_chat_clears_history(self):
        agent = ChatAgent(system_prompt="sys")
        provider = _DummyProvider(api_key="")
        agent.chat("Hi", None, provider, "m")
        agent.clear_history()
        assert len(agent._session._history) == 0

    def test_chat_uses_tools_when_provider_supports(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        agent = ChatAgent(system_prompt="sys", tools=[tool])
        provider = _ToolProvider(tool_response="searched")
        result = agent.chat("find something", None, provider, "m")
        assert result == "searched"
        assert len(provider.chat_with_tools_calls) == 1

    def test_chat_skips_tools_when_provider_does_not_support(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        agent = ChatAgent(system_prompt="sys", tools=[tool])
        provider = _DummyProvider(api_key="")
        result = agent.chat("hi", None, provider, "m")
        assert result == "dummy"

    def test_chat_prepends_context(self):
        captured: list = []

        class _CapturingProvider(_DummyProvider):
            def chat(self, messages, model):
                captured.extend(messages)
                return "ok"

        agent = ChatAgent(system_prompt="sys")
        agent.chat("question", "doc context", _CapturingProvider(api_key=""), "m")
        user_msg = next(m for m in captured if m["role"] == "user")
        assert "doc context" in user_msg["content"]


# ── Phase 3: NoteAssistAgent ──────────────────────────────────────────────────

class TestNoteAssistAgent:
    def test_run_without_tools_uses_chat(self):
        agent = NoteAssistAgent(system_prompt="Assist notes")
        provider = _DummyProvider(api_key="")
        result = agent.run("Improve this note", provider, "m")
        assert result == "dummy"

    def test_run_with_tools_uses_chat_with_tools(self):
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        agent = NoteAssistAgent(system_prompt="sys", tools=[tool])
        provider = _ToolProvider(tool_response="improved")
        result = agent.run("Improve note", provider, "m")
        assert result == "improved"


# ── Phase 3: DocumentAgent ────────────────────────────────────────────────────

class TestDocumentAgent:
    def test_run_without_tools(self):
        agent = DocumentAgent(system_prompt="Analyze doc")
        provider = _DummyProvider(api_key="")
        result = agent.run("Summarize", provider, "m")
        assert result == "dummy"

    def test_run_with_search_tool(self):
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        agent = DocumentAgent(system_prompt="sys", tools=[tool])
        provider = _ToolProvider(tool_response="analysis done")
        result = agent.run("Analyze", provider, "m")
        assert result == "analysis done"


# ── Phase 3: AIService agents ─────────────────────────────────────────────────

class TestAIServiceAgents:
    def test_configure_agents_replaces_chat_agent(self):
        svc = AIService(provider="ollama")
        old_agent = svc._chat_agent
        tool = NoteReadTool(list_notes_fn=lambda page=None: [])
        svc.configure_agents(chat_tools=[tool])
        assert svc._chat_agent is not old_agent
        assert "note_read" in svc._chat_agent.tools

    def test_configure_agents_replaces_note_agent(self):
        svc = AIService(provider="ollama")
        tool = NoteDeleteTool(delete_note_fn=lambda nid: None)
        svc.configure_agents(note_assist_tools=[tool])
        assert "note_delete" in svc._note_agent.tools

    def test_configure_agents_replaces_doc_agent(self):
        svc = AIService(provider="ollama")
        tool = DocumentSearchTool(search_fn=lambda q, page=None: [])
        svc.configure_agents(document_tools=[tool])
        assert "document_search" in svc._doc_agent.tools

    def test_chat_routes_through_chat_agent(self):
        svc = AIService(provider="ollama")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            result = svc.chat("hello")
        assert result == "dummy"

    def test_note_assist_routes_through_note_agent(self):
        svc = AIService(provider="ollama")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            result = svc.note_assist("my note", "quote", "improve")
        assert result == "dummy"

    def test_ai_action_routes_through_doc_agent(self):
        svc = AIService(provider="ollama")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            result = svc.ai_action("explain", "some text")
        assert result == "dummy"

    def test_quick_action_routes_through_doc_agent(self):
        svc = AIService(provider="ollama")
        mock_provider = _DummyProvider(api_key="")
        with patch.object(svc, "_get_provider", return_value=mock_provider):
            result = svc.quick_action("full_summary")
        assert result == "dummy"

    def test_chat_with_tool_provider_uses_tools(self):
        svc = AIService(provider="ollama")
        tool = NoteReadTool(list_notes_fn=lambda page=None: [{"id": "1"}])
        svc.configure_agents(chat_tools=[tool])
        tool_provider = _ToolProvider(tool_response="notes listed")
        with patch.object(svc, "_get_provider", return_value=tool_provider):
            result = svc.chat("what are my notes?")
        assert result == "notes listed"
        assert len(tool_provider.chat_with_tools_calls) == 1
