#!/usr/bin/env python3
"""
DeepRead AI - Entry Point (Web-Based UI)

This is the main entry point for the DeepRead AI application using PyWebView.
It provides a modern web-based UI with Python backend integration.
"""

import os
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import webview
except ImportError:
    print("Error: pywebview is not installed.")
    print("Install it with: pip install pywebview")
    sys.exit(1)

from backend import DeepReadAPI


def get_frontend_path() -> Path:
    """Get the path to the frontend directory."""
    return Path(__file__).parent / "frontend"


def main():
    """Main entry point."""
    print("Starting DeepRead AI...")
    print("=" * 50)

    # Check for required dependencies
    try:
        import fitz  # PyMuPDF
        print("✓ PyMuPDF (fitz) loaded")
    except ImportError:
        print("⚠ PyMuPDF not installed. PDF functionality will be limited.")
        print("  Install with: pip install PyMuPDF")

    try:
        from PIL import Image
        print("✓ Pillow (PIL) loaded")
    except ImportError:
        print("⚠ Pillow not installed. PDF rendering will not work.")
        print("  Install with: pip install Pillow")

    try:
        import openai
        if os.getenv("OPENAI_API_KEY"):
            print("✓ OpenAI API key configured")
        else:
            print("ℹ OpenAI API key not set (set OPENAI_API_KEY env var)")
    except ImportError:
        print("ℹ OpenAI library not installed (optional)")
        print("  Install with: pip install openai")

    # Create the API instance
    api = DeepReadAPI()

    # Get the frontend HTML path
    frontend_path = get_frontend_path()
    index_html = frontend_path / "index.html"

    if not index_html.exists():
        print(f"Error: Frontend not found at {index_html}")
        sys.exit(1)

    print(f"✓ Frontend loaded from: {frontend_path}")
    print("✓ Starting webview window...")
    print("=" * 50)

    # Create the window
    window = webview.create_window(
        title="DeepRead AI",
        url=str(index_html),
        width=1400,
        height=900,
        min_size=(900, 600),
        text_select=True,
        js_api=api,
    )

    # Expose the API to JavaScript
    api.window = window

    # Start the webview
    webview.start(
        debug=os.getenv("DEEPREAD_DEBUG", "false").lower() == "true",
        http_server=True,
    )

    print("\n✓ DeepRead AI closed")


if __name__ == "__main__":
    main()
