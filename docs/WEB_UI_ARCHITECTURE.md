# Web-Based UI Architecture for DeepRead AI

## Overview

Replace PySide6 with a modern web-based UI that runs as a desktop app. This gives you:

- **Beautiful, modern UI** - Full CSS, animations, modern fonts
- **True cross-platform** - Windows, Linux, Mac with identical look
- **Better ecosystem** - Rich text editors, PDF viewers, chat UIs already built
- **Smaller code** - Less UI code, more focus on core features

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Desktop Window (PyWebView)                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Modern Web UI (HTML/CSS/JS)                    │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │  PDF Viewer │  │  Note Editor │  │  AI Chat    │  │  │
│  │  │  (PDF.js)   │  │  (Monaco/    │  │  (Custom)   │  │  │
│  │  │             │  │   ProseMirror)│  │             │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────┴────────────────────────────────────┐
│                    Python Backend                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  PDF Engine │  │  AI Service  │  │  Database (SQLite)  │ │
│  │  (PyMuPDF)  │  │  (OpenAI/    │  │                     │ │
│  │             │  │   Ollama)    │  │                     │ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Technology Choices

### Frontend (Web)
- **Vanilla HTML/CSS/JS** - No framework needed for this app
- **PDF.js** - Mozilla's PDF viewer (better than Qt's)
- **Monaco Editor** - VS Code's editor for markdown
- **Socket.io** or simple HTTP API for Python communication

### Desktop Wrapper
- **PyWebView** - Uses native webview (Edge on Windows, WebKit on Linux/Mac)
  - Pros: Small size (~1MB), native feel, no bundled browser
  - Cons: Slightly different rendering per platform

**Alternative: Tauri**
- Rust-based, very small bundles
- But requires Rust knowledge

## Communication: Python ↔ Web UI

### Option 1: HTTP API (Simple)
```python
# Python backend
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/pdf/open', methods=['POST'])
def open_pdf():
    # ... open PDF
    return jsonify({"pages": 42, "current": 1})

@app.route('/api/ai/chat', methods=['POST'])
def chat():
    message = request.json['message']
    # ... send to AI
    return jsonify({"response": "..."})
```

```javascript
// Frontend
fetch('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify({message: "Summarize this"})
}).then(r => r.json()).then(data => {
    displayMessage(data.response);
});
```

### Option 2: PyWebView's JS API (Recommended)
```python
# Python exposes functions to JavaScript
import webview

class API:
    def open_pdf(self, path):
        # ... open PDF
        return {"pages": 42}

    def ai_chat(self, message):
        # ... chat with AI
        return "AI response here"

window = webview.create_window('DeepRead', 'index.html', js_api=API())
webview.start()
```

```javascript
// Frontend calls Python directly
const result = await pywebview.api.open_pdf('/path/to/file.pdf');
console.log(result.pages);  // 42

const response = await pywebview.api.ai_chat('Summarize this');
displayMessage(response);
```

## Migration Strategy

### Phase 1: Proof of Concept (1-2 days)
- [x] Create web UI demo (done - `web_ui_demo.py`)
- [ ] Add PyWebView integration
- [ ] Test PDF.js rendering
- [ ] Test Python ↔ JS communication

### Phase 2: Core Features (1 week)
- [ ] Port PDF viewer (PDF.js + PyMuPDF for text extraction)
- [ ] Port note editor (Monaco Editor or SimpleMDE)
- [ ] Port AI chat panel
- [ ] Implement file open/save

### Phase 3: Polish (1 week)
- [ ] Text selection with AI actions
- [ ] Citations and linking
- [ ] Theme/styling refinement
- [ ] Packaging for distribution

## File Structure

```
BetterPDF/
├── main.py                    # Entry point
├── backend/                   # Python backend
│   ├── __init__.py
│   ├── pdf_engine.py         # PyMuPDF wrapper
│   ├── ai_service.py         # AI integration
│   └── database.py           # SQLite
├── frontend/                  # Web UI
│   ├── index.html            # Main HTML
│   ├── css/
│   │   └── main.css          # Styles
│   ├── js/
│   │   ├── app.js            # Main app logic
│   │   ├── pdf-viewer.js     # PDF.js integration
│   │   ├── note-editor.js    # Markdown editor
│   │   └── ai-chat.js        # Chat UI
│   └── assets/               # Icons, fonts
└── requirements.txt
```

## Pros vs Cons

### Pros
- **Beautiful UI** - No Qt limitations, full modern CSS
- **Less code** - Rich components already built (editors, PDF viewers)
- **Cross-platform** - Identical look on all platforms
- **Easy to modify** - Edit HTML/CSS, restart, see changes
- **Future-proof** - Can deploy as web app later

### Cons
- **Dependency** - Requires webview or browser
- **Memory** - Slightly more RAM than Qt (but acceptable)
- **Rewrite** - Need to port existing UI code

## Recommendation

**Go with PyWebView + Web UI.**

The demo I created (`web_ui_demo.py`) shows the concept. Run it on your machine to see the modern dark UI.

The existing Qt code can be gradually migrated:
1. Keep the backend logic (PDF, AI, database)
2. Replace UI widgets with web equivalents
3. Connect via PyWebView's JS API

Want me to continue building this out?
