# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeepRead AI is a desktop PDF reader with OCR and AI integration. It uses a hybrid architecture: Python backend with a web-based UI running inside a native desktop window via PyWebView. Supports Windows packaging via PyInstaller with Inno Setup installer.

## Architecture

```
┌─────────────────────────────────────────────┐
│  WebView (HTML/CSS/JS) Frontend            │
│  ├─ PDF rendering as base64 PNG images     │
│  ├─ Markdown note editor                   │
│  └─ AI chat panel (multi-provider)         │
└──────────────┬──────────────────────────────┘
               │ pywebview.js_api
               ▼
┌─────────────────────────────────────────────┐
│  Python Backend                            │
│  ├─ DeepReadAPI (backend/api.py)           │
│  ├─ PDFEngine (backend/pdf_engine.py)      │
│  ├─ AIService (backend/ai_service.py)      │
│  ├─ PersistenceStore (backend/persistence.py) │
│  └─ OCR Engine (backend/ocr/)              │
└─────────────────────────────────────────────┘
```

**Key architectural decisions:**
- PyWebView exposes Python methods to JavaScript via `pywebview.api`
- PDF pages are rendered server-side to PNG and sent as base64 to the frontend
- SQLite persistence for session state, recent files, page notes, and AI settings
- No bundler - vanilla JavaScript for simplicity
- AI supports OpenAI, Anthropic, and Ollama providers with runtime switching
- OCR via PaddleOCR with mobile/server model variants and background processing

## Development Commands

```bash
# Install dependencies (preferred - uses uv)
uv sync --extra dev

# Or traditional pip
pip install -r requirements.txt

# Run the application
python main.py

# Run in debug mode (enables webview devtools)
DEEPREAD_DEBUG=true python main.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=backend

# Build Windows executable
powershell -File scripts/build_windows.ps1 -Version <version>
```

## Project Structure

```
BetterPDF/
├── main.py                    # Entry point - initializes PyWebView window
├── pyproject.toml             # Project metadata and dependencies (uv/hatch)
├── backend/                   # Python backend package
│   ├── api.py                # DeepReadAPI class exposed to JS
│   ├── pdf_engine.py         # PyMuPDF wrapper for PDF operations
│   ├── ai_service.py         # Multi-provider AI (OpenAI/Anthropic/Ollama)
│   ├── persistence.py        # SQLite persistence layer
│   └── ocr/                  # OCR subsystem
│       ├── engine.py         # PaddleOCR integration, model management
│       ├── pipeline.py       # OCR workflow orchestration
│       ├── normalize.py      # Coordinate normalization
│       └── rendering.py      # PDF page to image rendering
├── frontend/                  # Web UI (loaded by PyWebView)
│   ├── index.html            # Main HTML file
│   ├── css/main.css          # Stylesheet (dark/light themes)
│   └── js/
│       ├── api-client.js     # JS wrapper for Python API
│       ├── app.js            # Main application logic
│       └── pdf-viewer.js     # PDF viewer component
├── tests/                     # pytest test suite
├── scripts/                   # Build and utility scripts
├── installer/                 # Windows installer resources (Inno Setup)
└── docs/                      # Documentation
```

## API Communication Pattern

Python methods in `backend/api.py` are automatically exposed to JavaScript:

```python
# backend/api.py
class DeepReadAPI:
    def open_pdf(self, file_path: str) -> dict:
        return {"success": True, "page_count": 42}
```

```javascript
// frontend/js/api-client.js
const result = await pywebview.api.open_pdf('/path/to/file.pdf');
```

The `API` object in `api-client.js` wraps these calls with error handling and mock responses for development without PyWebView.

**Key API surface areas:**
- PDF operations: `open_pdf`, `get_page`, `get_text`, `search_text`
- OCR: `ocr_page`, `ocr_document`, `start_ocr_document`, `get_ocr_progress`
- Persistence: `get_recent_files`, `save_session_state`, `save_page_notes`, `delete_page_note`
- AI: `chat`, `ai_action`, `get_ai_settings`, `save_ai_settings`

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `OLLAMA_BASE_URL` - Ollama endpoint URL
- `DEEPREAD_DEBUG` - Set to `true` to enable webview devtools
- `DEEPREAD_PACKAGED` - Indicates frozen/packaged build
- `DEEPREAD_PORTABLE_MODE` - Enable portable mode (data stored alongside executable)
- `DEEPREAD_PORTABLE_DIR` - Custom portable data directory
- `DEEPREAD_DB_PATH` - Override SQLite database location
- `DEEPREAD_OCR_MODEL_DIR` - Override OCR model cache location

## Key Implementation Notes

- PDF rendering: Pages are rendered to PNG via PyMuPDF and sent as base64 data URLs
- Text selection: Implemented via overlay divs on the PDF image, coordinates mapped back to PDF space
- AI actions: Support explain, summarize, translate, define on selected text
- Notes: Support markdown with PDF citations via `[[pdf:doc#page=N]]` syntax
- Mock mode: API client returns mock data when not running in PyWebView (for browser development)
- OCR: PaddleOCR with mobile/server model pairs, intelligent model caching, fallback recovery for broken caches
- Persistence: SQLite in platform-specific data directory (`~/.local/share/deepread-ai` on Linux, `%APPDATA%` on Windows)

## Documentation

- `docs/architect.md` - Detailed architecture blueprint (Chinese)
- `docs/ocr_integration.md` - OCR integration guide
- `docs/windows_release.md` - Windows release process
- `docs/UI_IMPROVEMENTS.md` - Linux UI improvements and font recommendations
- `docs/WEB_UI_ARCHITECTURE.md` - Architecture proposal and migration strategy

## Communication

请用中文回复所有问题和说明。
