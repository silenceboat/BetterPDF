# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeepRead AI is a desktop PDF reader with AI integration. It uses a hybrid architecture: Python backend with a web-based UI running inside a native desktop window via PyWebView.

## Architecture

```
┌─────────────────────────────────────────────┐
│  WebView (HTML/CSS/JS) Frontend            │
│  ├─ PDF rendering as base64 PNG images     │
│  ├─ Markdown note editor                   │
│  └─ AI chat panel                          │
└──────────────┬──────────────────────────────┘
               │ pywebview.js_api
               ▼
┌─────────────────────────────────────────────┐
│  Python Backend                            │
│  ├─ DeepReadAPI (backend/api.py)           │
│  ├─ PDFEngine (backend/pdf_engine.py)      │
│  ├─ AIService (backend/ai_service.py)      │
│  └─ In-memory note storage                 │
└─────────────────────────────────────────────┘
```

**Key architectural decisions:**
- PyWebView exposes Python methods to JavaScript via `pywebview.api`
- PDF pages are rendered server-side to PNG and sent as base64 to the frontend
- No database - notes stored in-memory (SQLite planned)
- No bundler - vanilla JavaScript for simplicity
- Legacy PySide6 UI exists in `ui/` but is being phased out

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run in debug mode (enables webview devtools)
DEEPREAD_DEBUG=true python main.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=backend
```

## Project Structure

```
BetterPDF/
├── main.py                    # Entry point - initializes PyWebView window
├── backend/                   # Python backend package
│   ├── api.py                # DeepReadAPI class exposed to JS
│   ├── pdf_engine.py         # PyMuPDF wrapper for PDF operations
│   └── ai_service.py         # OpenAI/Ollama integration
├── frontend/                  # Web UI (loaded by PyWebView)
│   ├── index.html            # Main HTML file
│   ├── css/main.css          # Stylesheet (dark/light themes)
│   └── js/
│       ├── api-client.js     # JS wrapper for Python API
│       ├── app.js            # Main application logic
│       └── pdf-viewer.js     # PDF viewer component
└── ui/                       # Legacy PySide6 UI (being phased out)
```

## API Communication Pattern

Python methods in `backend/api.py` are automatically exposed to JavaScript:

```python
# backend/api.py
class DeepReadAPI:
    def open_pdf(self, file_path: str) -> dict:
        # Returns dict with success status and data
        return {"success": True, "page_count": 42}
```

```javascript
// frontend/js/api-client.js
const result = await pywebview.api.open_pdf('/path/to/file.pdf');
```

The `API` object in `api-client.js` wraps these calls with error handling and mock responses for development without PyWebView.

## Environment Variables

- `OPENAI_API_KEY` - Required for OpenAI integration
- `DEEPREAD_DEBUG` - Set to `true` to enable webview devtools

## Key Implementation Notes

- PDF rendering: Pages are rendered to PNG via PyMuPDF and sent as base64 data URLs
- Text selection: Implemented via overlay divs on the PDF image, coordinates mapped back to PDF space
- AI actions: Support explain, summarize, translate, define on selected text
- Notes: Support markdown with PDF citations via `[[pdf:doc#page=N]]` syntax
- Mock mode: API client returns mock data when not running in PyWebView (for browser development)

## Documentation

- `WEB_UI_ARCHITECTURE.md` - Architecture proposal and migration strategy
- `UI_IMPROVEMENTS.md` - Linux UI improvements and font recommendations
- `docs/architect.md` - Detailed architecture blueprint (Chinese)
