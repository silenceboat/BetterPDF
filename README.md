# DeepRead AI

A desktop PDF reader with OCR and AI integration, built with Python and PyWebView.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)

## Features

- **PDF Rendering** - Fast page rendering powered by PyMuPDF
- **OCR** - Extract text from scanned PDFs using PaddleOCR (mobile & server models)
- **AI Chat & Actions** - Multi-provider support: OpenAI-compatible, Anthropic-compatible, and Ollama
- **Markdown Notes** - Per-page notes with PDF citation syntax (`[[pdf:doc#page=N]]`)
- **Session Persistence** - Automatically saves and restores reading position, notes, and settings
- **Native Desktop Window** - Web-based UI running inside a native window via PyWebView

## Download

Go to the [Releases](https://github.com/ziyangly/BetterPDF/releases) page and download the latest version:

| File | Description |
|------|-------------|
| `BetterPDF-<version>-win-x64-setup.exe` | Windows installer (auto-installs WebView2 if missing) |
| `BetterPDF-<version>-win-x64-portable.zip` | Portable version, no installation required |

OCR models are pre-bundled in release builds - no additional downloads needed.

## Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended)

### Install & Run

```bash
# Install dependencies
uv sync --extra dev

# Run the application
uv run python main.py

# Debug mode (enables webview devtools)
DEEPREAD_DEBUG=true uv run python main.py
```

### Tests

```bash
uv run pytest -q
```

### Windows Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -Version 0.1.0
```

Releases are automated via GitHub Actions - push a version tag (`v*`) to trigger a build.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPREAD_DEBUG` | Enable webview debug mode |
| `DEEPREAD_PORTABLE_MODE` | Store app data near executable |
| `DEEPREAD_PORTABLE_DIR` | Custom portable data directory |
| `DEEPREAD_OCR_MODEL_DIR` | Override OCR model cache location |

## License

[MIT License](LICENSE)

---

# DeepRead AI 中文说明

桌面端 PDF 阅读器，集成 OCR 文字识别与 AI 辅助功能。基于 Python + PyWebView 构建。

## 功能特性

- **PDF 阅读** - 基于 PyMuPDF 的高速页面渲染
- **OCR 文字识别** - 使用 PaddleOCR 从扫描版 PDF 中提取文字，支持移动端/服务器端模型
- **AI 对话与操作** - 支持多种 AI 服务商：OpenAI 兼容接口、Anthropic 兼容接口、Ollama 本地模型
- **Markdown 笔记** - 按页记录笔记，支持 PDF 引用语法 (`[[pdf:doc#page=N]]`)
- **会话持久化** - 自动保存和恢复阅读位置、笔记及设置
- **原生桌面窗口** - Web UI 运行在 PyWebView 原生窗口中

## 下载安装

前往 [Releases](https://github.com/ziyangly/BetterPDF/releases) 页面下载最新版本：

| 文件 | 说明 |
|------|------|
| `BetterPDF-<version>-win-x64-setup.exe` | Windows 安装版（自动安装 WebView2） |
| `BetterPDF-<version>-win-x64-portable.zip` | 便携版，无需安装 |

发布版已内置 OCR 模型，首次使用无需额外下载。

## 本地开发

### 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（推荐）

### 安装与运行

```bash
# 安装依赖
uv sync --extra dev

# 运行应用
uv run python main.py

# 调试模式（启用 WebView 开发者工具）
DEEPREAD_DEBUG=true uv run python main.py
```

### 测试

```bash
uv run pytest -q
```

### Windows 打包

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -Version 0.1.0
```

通过 GitHub Actions 自动化发布——推送版本标签（`v*`）即可触发构建。

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPREAD_DEBUG` | 启用 WebView 调试模式 |
| `DEEPREAD_PORTABLE_MODE` | 便携模式，数据存储在程序目录旁 |
| `DEEPREAD_PORTABLE_DIR` | 自定义便携数据目录 |
| `DEEPREAD_OCR_MODEL_DIR` | 自定义 OCR 模型缓存路径 |

## 许可证

[MIT License](LICENSE)
