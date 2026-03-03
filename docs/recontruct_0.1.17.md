# AI 模块重构设计 v0.1.17

## 背景与动机

当前 `backend/ai/service.py` 承担了过多本应属于各 provider 的职责。具体问题：

1. **Provider 相关逻辑集中在 service 层**：`_get_default_model`、`_get_provider_env_key`、`_resolve_api_key`、`_get_provider` 这四个方法都包含 `if self.provider == "openai" / "anthropic" / "ollama"` 的分支判断。如果要新增一个 provider（如 Google Gemini），需要在 service.py 里改动 4 处，违反开闭原则。

2. **Provider 没有自校验能力**：校验逻辑（如"是否有 API key"）散落在 `_get_provider` 和各 provider 的 `chat` 方法中，没有统一的校验入口。用户配错参数时无法在调用前就给出清晰的错误提示。

3. **Chat 上下文管理粗糙**：当前 `_history` 直接用 list 存储，硬截断最近 10 轮（`_history[-20:]`）。这种方式无法区分普通对话和 action 调用的上下文，也不利于未来扩展 tool use。

4. **各 assistant 只是换 prompt，没有行为差异**：`ai_action`、`quick_action`、`note_assist` 三个方法本质上只是拼接不同 prompt 后调 `chat`，没有独立的工具调用或多步推理能力。

## 目标

1. 让每个 provider 自己负责默认模型、环境变量、参数校验，service 层只做路由和编排
2. 为 chat 上下文管理预留 tool use 的扩展空间（本次不实现 tool use，只做结构准备）
3. 为 assistant → agent 的演进做架构准备（本次实现基础 tool 接口）

## 非目标（边界）

- **不改前端调用接口**：`api.py` 中 `chat`、`ai_action`、`quick_action`、`note_assist`、`get_ai_settings`、`save_ai_settings` 的函数签名和返回格式保持不变
- **不改 persistence 层**：SQLite 存储结构不变
- **不新增 AI provider**：只重构现有的 openai / anthropic / ollama
- **不实现完整的 agent 自主决策**：Phase 3 只搭建 tool 注册和调用框架，不做多步自主规划

## 方案设计

### 当前架构

```
AIService（service.py）
├── 配置管理：_get_default_model, _normalize_provider, _resolve_api_key, ...
├── Provider 工厂：_get_provider()  ← if/elif 分支
├── Chat：chat() + _history 列表
├── Actions：ai_action(), quick_action(), note_assist()  ← 纯 prompt 拼接
└── Mock 降级：_mock_response()

BaseProvider（base.py）
└── 只有一个抽象方法：chat(messages, model) -> str

各 Provider（openai.py, anthropic.py, ollama.py）
└── 只实现 chat，不管配置和校验
```

### 目标架构

```
AIService（service.py）—— 只做路由和编排
├── configure() / get_config()  ← 委托给 provider
├── chat()                      ← 委托给 ChatSession
├── ai_action() / quick_action() / note_assist()  ← 委托给 Agent
└── Provider 注册表             ← 替代 if/elif

BaseProvider（base.py）—— 扩展职责
├── chat(messages, model) -> str       [抽象]
├── default_model() -> str             [抽象]
├── env_key() -> str                   [抽象]
├── validate() -> (bool, str)          [抽象]
├── resolve_api_key() -> str           [通用实现]
└── normalize_base_url() -> str        [通用实现]

ChatSession（新增）—— 管理对话上下文
├── messages: list[Message]
├── add_user_message() / add_assistant_message()
├── build_request_messages() -> list   ← 组装 system + history + 当前消息
└── truncate()                         ← 上下文截断策略

Tool / Agent（新增）—— 基础框架
├── Tool: execute(**params) -> dict    [抽象接口]
├── NoteReadTool / NoteWriteTool / NoteDeleteTool  [具体工具]
└── Agent: 持有 tools 列表，可按需调用
```

### Phase 1：Provider 自治化

**目标**：让 provider 自己管理配置和校验，service 不再包含 provider 特有逻辑。

**步骤**：

1. 扩展 `base.py`，定义新接口：

```python
class BaseProvider(ABC):
    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key
        self.base_url = self._normalize_base_url(base_url)

    @abstractmethod
    def chat(self, messages: list[dict], model: str) -> str: ...

    @staticmethod
    @abstractmethod
    def default_model() -> str:
        """该 provider 的默认模型名"""
        ...

    @staticmethod
    @abstractmethod
    def env_key() -> str:
        """该 provider 对应的环境变量名，如 'OPENAI_API_KEY'"""
        ...

    def validate(self) -> tuple[bool, str]:
        """校验当前配置是否可用，返回 (是否合法, 错误信息)"""
        resolved = self.resolve_api_key()
        if not resolved:
            return False, f"Missing API key. Set it in Settings or {self.env_key()}"
        return True, ""

    def resolve_api_key(self) -> str:
        return self.api_key or os.getenv(self.env_key(), "")

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        return str(base_url or "").strip().rstrip("/")
```

2. 各 provider 实现新接口：

```python
# openai.py
class OpenAIProvider(BaseProvider):
    @staticmethod
    def default_model() -> str:
        return "gpt-4o-mini"

    @staticmethod
    def env_key() -> str:
        return "OPENAI_API_KEY"

# anthropic.py — 同理，default_model 返回 "claude-3-5-haiku-latest"
# ollama.py — env_key 返回 "OLLAMA_API_KEY"，validate 不强制要求 API key
```

3. service.py 中用注册表替代 if/elif：

```python
class AIService:
    _PROVIDERS: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    def _get_provider(self) -> BaseProvider | None:
        cls = self._PROVIDERS.get(self.provider)
        if cls is None:
            return None
        instance = cls(api_key=self._resolve_api_key(), base_url=self.base_url)
        ok, err = instance.validate()
        if not ok:
            return None
        return instance
```

4. 删除 service.py 中的 `_get_default_model`、`_get_provider_env_key`、`_resolve_api_key`，改为调用 provider 的对应方法。

**验收标准**：
- `pytest` 全部通过
- 手动测试：切换 openai / anthropic / ollama 三种 provider 的配置保存和 chat 调用正常
- service.py 中不再包含任何 provider 名称的 if/elif 判断

### Phase 2：Chat 上下文管理重构

**目标**：将对话历史管理从 service 中抽离为独立的 `ChatSession`，为未来 tool use 预留结构。

**本次只做结构拆分，不改变行为**。当前的截断逻辑（最近 10 轮）保持不变。

**步骤**：

1. 新建 `backend/ai/chat_session.py`：

```python
@dataclass
class Message:
    role: str          # "system" | "user" | "assistant" | "tool" (未来)
    content: str

class ChatSession:
    def __init__(self, system_prompt: str, max_turns: int = 10):
        self._system = Message(role="system", content=system_prompt)
        self._history: list[Message] = []
        self._max_turns = max_turns

    def add(self, role: str, content: str) -> None:
        self._history.append(Message(role=role, content=content))

    def build_messages(self, user_content: str) -> list[dict]:
        """组装完整的 messages 列表，供 provider.chat() 使用"""
        recent = self._history[-(self._max_turns * 2):]
        return (
            [{"role": "system", "content": self._system.content}]
            + [{"role": m.role, "content": m.content} for m in recent]
            + [{"role": "user", "content": user_content}]
        )

    def clear(self) -> None:
        self._history.clear()
```

2. service.py 的 `chat` 方法改为使用 `ChatSession`：

```python
def chat(self, message: str, context: str | None = None) -> str:
    user_content = f"Context from document:\n{context}\n\nUser question: {message}" if context else message
    messages = self._session.build_messages(user_content)
    provider = self._get_provider()
    if provider is None:
        return self._mock_response(message, context)
    response = provider.chat(messages, self.model)
    self._session.add("user", user_content)
    self._session.add("assistant", response)
    return response
```

**验收标准**：
- 行为与重构前完全一致（同样的输入产生同样的输出）
- `_history` 列表不再出现在 service.py 中

### Phase 3：Tool 和 Agent 基础框架

**目标**：定义 Tool 抽象接口，实现笔记相关工具，让 `note_assist` 可以通过 tool 调用操作笔记。

**步骤**：

1. 新建 `backend/ai/tools.py`，定义 Tool 接口：

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称，如 'note_read'"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，供 AI 理解用途"""
        ...

    @abstractmethod
    def execute(self, **params) -> dict:
        """执行工具，返回结果字典"""
        ...

class NoteReadTool(Tool):
    name = "note_read"
    description = "Read the content of the current note"

    def __init__(self, get_note_fn):
        self._get_note = get_note_fn  # 注入，来自 api.py

    def execute(self, **params) -> dict:
        note = self._get_note()
        return {"content": note or ""}

class NoteWriteTool(Tool):
    name = "note_write"
    description = "Write or update the current note content"

    def __init__(self, save_note_fn):
        self._save_note = save_note_fn

    def execute(self, content: str = "", **params) -> dict:
        self._save_note(content)
        return {"success": True}
```

2. 新建 `backend/ai/agent.py`，定义 Agent 基类：

```python
class Agent:
    def __init__(self, name: str, system_prompt: str, tools: list[Tool] | None = None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = {t.name: t for t in (tools or [])}

    def run(self, user_input: str, provider: BaseProvider, model: str) -> str:
        """单轮执行：发送消息给 AI，本次不做多步 tool 调用循环"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        return provider.chat(messages, model)
```

3. `note_assist` 改为使用 `NoteAssistAgent`（Agent 的子类），但**保持原有行为**——Agent 框架搭好，tool 调用循环留待后续实现。

**验收标准**：
- `note_assist` 行为不变
- Tool 接口已定义，NoteReadTool / NoteWriteTool 可以被实例化和调用
- Agent 基类可以注册 tools 并通过 `run` 方法调用 provider

## 风险与兼容性

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重构后 provider 行为不一致 | chat 功能异常 | 现有测试覆盖 + 手动测试三种 provider |
| api.py 调用方式变化 | 前端功能异常 | api.py 的公开方法签名不变，只改内部调用 |
| OllamaProvider.validate 误拒 | 本地 Ollama 用户无法使用 | Ollama 的 validate 不强制 API key |
| AI 测试覆盖不足 | 重构引入的 bug 难以发现 | Phase 1 完成后补充 `test_ai_service.py` |

## 文件变更清单

```
修改：
  backend/ai/service.py       ← 删除 provider 特有逻辑，使用注册表和 ChatSession
  backend/ai/providers/base.py ← 扩展抽象接口
  backend/ai/providers/openai.py     ← 实现 default_model, env_key, validate
  backend/ai/providers/anthropic.py  ← 同上
  backend/ai/providers/ollama.py     ← 同上，validate 不强制 key

新增：
  backend/ai/chat_session.py  ← 对话上下文管理
  backend/ai/tools.py         ← Tool 抽象接口和笔记工具实现
  backend/ai/agent.py         ← Agent 基类
  tests/test_ai_service.py    ← AI 模块测试

不变：
  backend/api.py              ← 公开方法签名不变
  backend/persistence.py      ← 不修改
  frontend/                   ← 不修改
```

## 开放问题

1. **Agent 的 tool 调用协议**：未来 agent 需要多步 tool 调用时，是采用 OpenAI 的 function calling 格式，还是自定义一套 JSON 协议？这取决于是否要支持不同 provider 的原生 tool use 能力。留待 Phase 3 实施时决定。
2. **上下文窗口管理策略**：当前按轮数截断，未来是否需要按 token 数截断？这取决于是否需要支持长文档分析。暂不改动。
