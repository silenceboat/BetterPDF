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


def _version_gte(current: str, required: str) -> bool:
    """Return True if current version is >= required version."""
    current_parts = [int(p) for p in current.split(".") if p.isdigit()]
    required_parts = [int(p) for p in required.split(".") if p.isdigit()]
    length = max(len(current_parts), len(required_parts))
    current_parts.extend([0] * (length - len(current_parts)))
    required_parts.extend([0] * (length - len(required_parts)))
    return current_parts >= required_parts


def _has_webview2_runtime() -> bool:
    """
    Check whether Microsoft Edge WebView2 runtime is installed on Windows.
    """
    if os.name != "nt":
        return True

    try:
        import winreg
    except Exception:
        return False

    guids = [
        "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",  # runtime
        "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # beta
        "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",  # dev
        "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",  # canary
    ]
    minimum = "86.0.622.0"
    key_roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)

    for root in key_roots:
        for guid in guids:
            candidate_paths = [rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"]
            # On 64-bit Windows, WebView2 can be registered under WOW6432Node.
            if root == winreg.HKEY_LOCAL_MACHINE:
                candidate_paths.append(
                    rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"
                )

            for key_path in candidate_paths:
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        version, _ = winreg.QueryValueEx(key, "pv")
                    if _version_gte(str(version), minimum):
                        return True
                except Exception:
                    continue

    return False


def main():
    """Main entry point."""
    print("Starting DeepRead AI...")
    print("=" * 50)

    # Quick dependency check (imports deferred to avoid slow startup)
    try:
        import fitz  # PyMuPDF - core dependency, check early
        print("✓ PyMuPDF available")
    except ImportError:
        print("⚠ PyMuPDF not installed. Install with: pip install PyMuPDF")

    if os.getenv("OPENAI_API_KEY"):
        print("✓ OpenAI API key configured")
    else:
        print("ℹ OpenAI API key not set (set OPENAI_API_KEY env var)")

    if os.name == "nt" and not _has_webview2_runtime():
        print("✗ Microsoft Edge WebView2 Runtime not found.")
        print("  Please install it, then restart DeepRead AI:")
        print("  https://developer.microsoft.com/en-us/microsoft-edge/webview2/")
        sys.exit(1)

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

    # Keep window reference on a private attribute to avoid pywebview
    # recursively introspecting a huge WinForms object graph.
    api._window = window

    def _on_webview_started():
        renderer = getattr(webview, "renderer", "unknown")
        print(f"✓ WebView renderer: {renderer}")
        if os.name == "nt" and renderer == "mshtml":
            print("⚠ Detected legacy MSHTML renderer. Install WebView2 Runtime for full compatibility.")

    # Start the webview
    webview.start(
        _on_webview_started,
        debug=os.getenv("DEEPREAD_DEBUG", "false").lower() == "true",
        http_server=True,
    )

    print("\n✓ DeepRead AI closed")


if __name__ == "__main__":
    main()
