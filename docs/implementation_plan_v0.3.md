# 实现计划：文档兼容性 + AI 激活码系统（v0.3）

## 背景

DeepRead AI 目前只支持 PDF 文件，且 AI 服务需要用户自行配置 API key。本次改动有两个目标：
1. 增加 DOCX 和 TXT 文件支持，所有格式统一以分页 PNG 图片方式显示
2. 将 AI 设置从"用户自配 API key"改为"激活码"模式，为后续额度管理做准备

---

## 第一部分：文档兼容性（DOCX + TXT）

### 思路

所有文档类型统一渲染为分页 PNG 图片，复用现有前端 viewer。通过工厂模式创建不同的 Engine，对 `api.py` 的改动最小化。

### 步骤

#### 1.1 新建 `backend/document_engine.py` — 抽象协议

定义 `DocumentEngine` Protocol，包含 `PDFEngine` 已有的所有公共方法签名：
- `file_path: str`, `page_count: int`
- `get_metadata() -> dict`
- `render_page(page_num, zoom) -> str` (base64 PNG)
- `extract_text(page_num, rect) -> str`
- `search_text(query, page_num) -> list`
- `get_page_size(page_num) -> tuple[float, float]`
- `close()`

`PDFEngine` 已隐式满足此协议，无需修改。

#### 1.2 新建 `backend/text_engine.py` — TXT 渲染引擎

- 读取文本文件（编码检测：UTF-8 → GBK → Latin-1）
- 按行分页（US Letter 尺寸 612×792pt，约 50 行/页）
- 用 Pillow 渲染每页为白底黑字 PNG
- 字体：Windows 用 `msyh.ttc`（微软雅黑），Linux 用 DejaVu Sans Mono，优先使用系统中文字体
- `extract_text` 直接返回对应页的文本
- `search_text` 在分页文本中搜索

#### 1.3 新建 `backend/docx_engine.py` — DOCX 渲染引擎

- 使用 `python-docx` 解析 DOCX 文件结构（段落、文本、样式）
- 用 Pillow 渲染每页为 PNG，类似 TXT Engine 的实现
- 页面尺寸：US Letter (612×792pt)
- 支持基本文本样式（字体、加粗、斜体、字号）
- 支持段落格式（对齐、缩进、行距）
- 字体回退：Windows 用 `msyh.ttc`（微软雅黑），Linux 用 DejaVu Sans + 系统中文字体
- `extract_text` 从 `python-docx` 段落中提取
- `search_text` 在文档段落中搜索
- 纯 Python 实现，无需外部应用依赖，适合打包分发

#### 1.4 新建 `backend/engine_factory.py` — 工厂函数

```python
def create_engine(file_path: str) -> DocumentEngine:
    ext = Path(file_path).suffix.lower()
    if ext == '.pdf': return PDFEngine(file_path)
    elif ext == '.docx': return DocxEngine(file_path)
    elif ext == '.txt': return TextEngine(file_path)
    else: raise ValueError(f"Unsupported file type: {ext}")
```

#### 1.5 修改 `backend/api.py`

- 导入 `create_engine` 替代直接使用 `PDFEngine`
- `open_pdf()` 第 89 行：`PDFEngine(normalized_path)` → `create_engine(normalized_path)`
- `open_pdf()` 返回值增加 `"supports_ocr": isinstance(self.pdf_engine, PDFEngine)`
- `_select_pdf_file_windows()` 第 807 行：文件过滤器改为 `"Supported Files (*.pdf;*.docx;*.txt)|*.pdf;*.docx;*.txt|PDF (*.pdf)|*.pdf|Word (*.docx)|*.docx|Text (*.txt)|*.txt|All (*.*)|*.*"`
- `select_pdf_file()` 第 879 行：pywebview 过滤器同步更新

#### 1.6 前端标签更新（最小改动）

- `frontend/index.html`：按钮文字 "Open PDF" → "Open File"
- `frontend/js/pdf-viewer.js`：占位符 "No PDF Open" → "No Document Open"
- `frontend/js/app.js`：toast 消息更新；根据 `supports_ocr` 控制 OCR 按钮显示/隐藏

#### 1.7 依赖更新

`pyproject.toml` 添加依赖：
```toml
[project]
dependencies = [
    # 现有依赖...
    "python-docx>=1.1.0",  # DOCX 解析
    # Pillow 已有，复用
]
```

---

## 第二部分：AI 激活码系统

### 思路

将 AI 设置 UI 从"用户配置 provider/key/URL"简化为"输入激活码"。开发者的 API 配置通过环境变量注入（开发阶段）或未来通过代理服务器转发。保留高级设置作为折叠选项，兼容现有用户。

### 架构说明

```
当前版本：
  用户输入激活码 → 本地存储 → 使用环境变量中的 API 配置 + 激活码

未来版本（额度管理）：
  用户输入激活码 → 请求发到代理服务器 → 服务器验证激活码+扣额度 → 转发给 AI 提供商
```

### 步骤

#### 2.1 扩展 `backend/persistence.py`

在现有 `app_settings` 表中添加两个方法：
- `save_activation_code(code: str)` — 存储激活码
- `get_activation_code() -> str` — 读取激活码

无需 schema 迁移，复用现有 `setting_key/setting_value` 结构。

#### 2.2 新建 `backend/activation.py`

```python
class ActivationManager:
    def __init__(self, persistence):
        self._code = persistence.get_activation_code()

    @property
    def is_activated(self) -> bool

    def set_code(self, code: str)      # 存储激活码
    def validate_format(self, code)     # 本地格式校验
    def get_ai_config(self) -> dict     # 返回 provider/model/url/key（从环境变量读取）
```

环境变量：
- `DEEPREAD_AI_API_KEY` — 开发者的 API key（不嵌入到应用中）
- `DEEPREAD_AI_PROXY_URL` — AI 代理服务器地址（未来使用）
- `DEEPREAD_AI_MODEL` — 默认模型

#### 2.3 修改 `backend/ai_service.py`

- `__init__` 和 `configure()` 增加 `activation_code` 参数
- 在请求头中附带 `X-Activation-Code`（为代理服务器预留）
- `get_config()` 返回 `is_activated` 状态

#### 2.4 修改 `backend/api.py`

- `__init__` 中初始化 `ActivationManager`
- 激活码存在时，用 `ActivationManager.get_ai_config()` 配置 `AIService`
- 无激活码时，回退到现有的用户自配设置（向后兼容）
- 新增 API 方法：
  - `get_activation_status() -> dict` — 返回激活状态
  - `save_activation_code(code) -> dict` — 存储并应用激活码
  - `clear_activation_code() -> dict` — 清除激活码

#### 2.5 修改 `frontend/js/api-client.js`

添加 mock 和调用方法：
- `getActivationStatus()`
- `saveActivationCode(code)`
- `clearActivationCode()`

#### 2.6 修改 `frontend/js/app.js` — 设置面板重构

设置面板分为两个区域：

**区域 1：激活码（主要）**
- 激活码输入框 + "激活"按钮
- 激活状态显示（已激活/未激活）
- "清除激活"按钮

**区域 2：高级设置（折叠）**
- 保留现有的 provider/model/URL/key 配置
- 当激活码生效时，显示"已被激活码覆盖"并禁用输入
- 无激活码时可正常使用（兼容高级用户）

---

## 实施顺序

两部分互相独立，建议按以下顺序实施：

1. **文档兼容性**（Part 1）
   - 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7
2. **AI 激活码**（Part 2）
   - 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6

## 新建文件清单

- `backend/document_engine.py`
- `backend/text_engine.py`
- `backend/docx_engine.py`
- `backend/engine_factory.py`
- `backend/activation.py`

## 修改文件清单

- `backend/api.py` — 工厂模式 + 激活码接口
- `backend/ai_service.py` — activation_code 支持
- `backend/persistence.py` — 激活码存储
- `frontend/js/app.js` — 设置面板重构 + 标签更新
- `frontend/js/api-client.js` — 新 API 方法
- `frontend/js/pdf-viewer.js` — 标签更新
- `frontend/index.html` — 按钮文字更新
- `pyproject.toml` — 可选依赖

## 验证方式

1. 打开 PDF、DOCX、TXT 文件，确认都能分页显示
2. TXT 文件中文内容正确渲染
3. DOCX 转换失败时有清晰错误提示
4. 输入激活码后 AI 功能可用
5. 清除激活码后回退到手动配置模式
6. 运行 `pytest` 确保现有测试不被破坏

## 关于 PPT 支持

PPT 的复杂度确实更高：幻灯片有动画、嵌入媒体、母版布局等。但技术路径与 DOCX 一致 — 转为临时 PDF 后复用现有管线。可以在完成 DOCX 支持后，以相同模式低成本添加。建议放到下一版。
