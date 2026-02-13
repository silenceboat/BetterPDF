# DeepRead AI

A desktop PDF reader with AI integration, built with Python and PyWebView.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **PDF Rendering**: View PDFs as high-quality rendered images
- **AI Integration**: Chat with AI about your PDF content using OpenAI or Ollama
- **Smart Text Selection**: Select text on PDFs for AI actions (explain, summarize, translate, define)
- **Markdown Notes**: Take notes with markdown support and PDF citations
- **Dark/Light Themes**: Comfortable reading experience

## Architecture

DeepRead uses a hybrid architecture:
- **Backend**: Python with PyMuPDF for PDF processing
- **Frontend**: Web-based UI (HTML/CSS/JS) running inside PyWebView
- **Communication**: pywebview.js_api for Python-JavaScript interop

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
│  └─ AIService (backend/ai_service.py)      │
└─────────────────────────────────────────────┘
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/BetterPDF.git
cd BetterPDF
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key (optional, for AI features):
```bash
export OPENAI_API_KEY="your-api-key"
```

## Usage

Run the application:
```bash
python main.py
```

Debug mode (enables webview devtools):
```bash
DEEPREAD_DEBUG=true python main.py
```

## Development

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=backend
```

## Project Structure

```
BetterPDF/
├── main.py                    # Entry point
├── backend/                   # Python backend
│   ├── api.py                # API exposed to JS
│   ├── pdf_engine.py         # PDF operations
│   └── ai_service.py         # AI integration
├── frontend/                  # Web UI
│   ├── index.html
│   ├── css/main.css
│   └── js/
│       ├── api-client.js
│       ├── app.js
│       └── pdf-viewer.js
└── ui/                       # Legacy PySide6 UI (phasing out)
```

## License

MIT License - see [LICENSE](LICENSE) for details.
