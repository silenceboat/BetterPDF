"""
Proof-of-concept: Web-based UI for DeepRead AI using PyWebView.

This demonstrates how to replace PySide6 with a modern web UI while
keeping all the Python backend logic.
"""

import json
import webview
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os


# HTML/CSS/JS for the modern UI
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DeepRead AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg-primary: #0f0f11;
            --bg-secondary: #1a1a1e;
            --bg-tertiary: #252529;
            --accent: #6366f1;
            --accent-hover: #818cf8;
            --text-primary: #fafafa;
            --text-secondary: #a1a1aa;
            --border: #27272a;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }

        .app {
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 64px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px 0;
            gap: 8px;
        }

        .sidebar-btn {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            transition: all 0.2s;
        }

        .sidebar-btn:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .sidebar-btn.active {
            background: var(--accent);
            color: white;
        }

        /* Main Content */
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Header */
        .header {
            height: 56px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            padding: 0 20px;
            gap: 16px;
        }

        .logo {
            font-weight: 700;
            font-size: 18px;
            background: linear-gradient(135deg, var(--accent), #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .search-box {
            flex: 1;
            max-width: 400px;
            position: relative;
        }

        .search-box input {
            width: 100%;
            height: 36px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0 12px 0 36px;
            color: var(--text-primary);
            font-size: 14px;
        }

        .search-box input::placeholder {
            color: var(--text-secondary);
        }

        .header-actions {
            display: flex;
            gap: 8px;
        }

        .btn {
            height: 36px;
            padding: 0 16px;
            border-radius: 8px;
            border: none;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary {
            background: var(--accent);
            color: white;
        }

        .btn-primary:hover {
            background: var(--accent-hover);
        }

        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--border);
        }

        /* Content Area */
        .content {
            flex: 1;
            display: flex;
            overflow: hidden;
        }

        /* PDF Viewer */
        .pdf-panel {
            flex: 1;
            background: #0a0a0c;
            display: flex;
            flex-direction: column;
            position: relative;
        }

        .pdf-toolbar {
            height: 44px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 12px;
        }

        .pdf-toolbar button {
            width: 32px;
            height: 32px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 16px;
        }

        .pdf-toolbar button:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .page-info {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .page-info input {
            width: 50px;
            height: 28px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            text-align: center;
            color: var(--text-primary);
        }

        .pdf-viewport {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: auto;
            padding: 40px;
        }

        .pdf-page {
            width: 600px;
            height: 800px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #333;
            font-size: 24px;
        }

        /* Right Panel */
        .right-panel {
            width: 380px;
            background: var(--bg-secondary);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
        }

        .panel-tabs {
            height: 48px;
            display: flex;
            border-bottom: 1px solid var(--border);
        }

        .panel-tab {
            flex: 1;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .panel-tab:hover {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .panel-tab.active {
            color: var(--accent);
            border-bottom: 2px solid var(--accent);
        }

        .panel-content {
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        /* Chat Panel */
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .message {
            max-width: 90%;
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.6;
        }

        .message.user {
            align-self: flex-end;
            background: var(--accent);
            color: white;
        }

        .message.ai {
            align-self: flex-start;
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .chat-input-area {
            padding: 16px;
            border-top: 1px solid var(--border);
        }

        .chat-input {
            display: flex;
            gap: 8px;
        }

        .chat-input textarea {
            flex: 1;
            height: 44px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            color: var(--text-primary);
            font-size: 14px;
            resize: none;
            font-family: inherit;
        }

        .chat-input textarea:focus {
            outline: none;
            border-color: var(--accent);
        }

        .chat-input button {
            width: 44px;
            height: 44px;
            border-radius: 8px;
            border: none;
            background: var(--accent);
            color: white;
            cursor: pointer;
            font-size: 18px;
        }

        .chat-input button:hover {
            background: var(--accent-hover);
        }

        /* Quick Actions */
        .quick-actions {
            padding: 12px 16px;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            border-bottom: 1px solid var(--border);
        }

        .quick-action {
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-size: 12px;
            cursor: pointer;
            white-space: nowrap;
        }

        .quick-action:hover {
            border-color: var(--accent);
            color: var(--accent);
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        <nav class="sidebar">
            <button class="sidebar-btn active" title="PDF Viewer">📄</button>
            <button class="sidebar-btn" title="Notes">📝</button>
            <button class="sidebar-btn" title="AI Chat">✨</button>
            <button class="sidebar-btn" title="Settings" style="margin-top: auto;">⚙</button>
        </nav>

        <!-- Main Content -->
        <div class="main">
            <!-- Header -->
            <header class="header">
                <div class="logo">DeepRead AI</div>
                <div class="search-box">
                    <input type="text" placeholder="Search in document...">
                </div>
                <div class="header-actions">
                    <button class="btn btn-secondary">📂 Open PDF</button>
                    <button class="btn btn-primary">💾 Save</button>
                </div>
            </header>

            <!-- Content -->
            <div class="content">
                <!-- PDF Panel -->
                <div class="pdf-panel">
                    <div class="pdf-toolbar">
                        <button>←</button>
                        <button>→</button>
                        <div class="page-info">
                            <span>Page</span>
                            <input type="text" value="1">
                            <span>/ 42</span>
                        </div>
                        <div style="margin-left: auto; display: flex; gap: 4px;">
                            <button>−</button>
                            <span style="color: var(--text-secondary); font-size: 13px; min-width: 50px; text-align: center;">100%</span>
                            <button>+</button>
                        </div>
                    </div>
                    <div class="pdf-viewport">
                        <div class="pdf-page">
                            PDF Page Content
                        </div>
                    </div>
                </div>

                <!-- Right Panel -->
                <div class="right-panel">
                    <div class="panel-tabs">
                        <button class="panel-tab">Notes</button>
                        <button class="panel-tab active">AI Chat</button>
                    </div>
                    <div class="panel-content">
                        <div class="quick-actions">
                            <button class="quick-action">📋 Summary</button>
                            <button class="quick-action">🎯 Key Points</button>
                            <button class="quick-action">❓ Questions</button>
                        </div>
                        <div class="chat-container">
                            <div class="chat-messages">
                                <div class="message ai">
                                    Hello! I'm your AI reading assistant. Select text from the PDF to analyze it, or ask me anything about the document.
                                </div>
                                <div class="message user">
                                    Summarize the main points of this paper
                                </div>
                                <div class="message ai">
                                    Based on the document, here are the key findings:
                                    <br><br>
                                    1. <strong>Novel Architecture</strong>: The paper introduces a new transformer variant with 40% better efficiency.<br>
                                    2. <strong>Benchmark Results</strong>: State-of-the-art on 5 major NLP tasks.<br>
                                    3. <strong>Ablation Studies</strong>: Detailed analysis shows attention mechanism is key.
                                </div>
                            </div>
                            <div class="chat-input-area">
                                <div class="chat-input">
                                    <textarea placeholder="Ask about this document..."></textarea>
                                    <button>➤</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simple interactivity
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
            });
        });

        document.querySelectorAll('.sidebar-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Auto-resize textarea
        const textarea = document.querySelector('.chat-input textarea');
        textarea.addEventListener('input', () => {
            textarea.style.height = '44px';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        });
    </script>
</body>
</html>
"""


class RequestHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to serve the web UI."""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode())

    def log_message(self, format, *args):
        pass  # Suppress logs


def start_server(port=8765):
    """Start the HTTP server in a thread."""
    server = HTTPServer(('localhost', port), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    """Main entry point."""
    print("Starting DeepRead AI - Web UI Demo")
    print("=" * 50)

    # Start the web server
    server = start_server(8765)
    print("✓ Web server started on http://localhost:8765")

    # Create the desktop window using pywebview
    try:
        import webview
        print("✓ Starting desktop window...")

        window = webview.create_window(
            title='DeepRead AI',
            url='http://localhost:8765',
            width=1400,
            height=900,
            min_size=(900, 600),
            text_select=True,
        )

        webview.start(debug=True)

    except ImportError:
        print("\n⚠️  pywebview not installed")
        print("Install with: pip install pywebview")
        print("\nOpening in default browser instead...")
        import webbrowser
        webbrowser.open('http://localhost:8765')
        input("Press Enter to stop the server...")

    finally:
        server.shutdown()
        print("\n✓ Server stopped")


if __name__ == '__main__':
    main()
