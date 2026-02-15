# BetterPDF (DeepRead AI)

A desktop PDF reader with OCR and AI integration, built with Python + PyWebView.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- PDF rendering with `PyMuPDF`
- OCR for scanned PDFs with `PaddleOCR`
- AI chat/actions (OpenAI-compatible, Anthropic, Ollama)
- Notes + session persistence
- Web-based UI in a native desktop window (`pywebview`)

## Windows Download (End Users)

Use the GitHub **Releases** page assets:

- `BetterPDF-<version>-win-x64-setup.exe` (installer)
- `BetterPDF-<version>-win-x64-portable.zip` (portable)

Behavior of release builds:

- OCR models are pre-bundled in the package.
- First OCR run does not require downloading Paddle models.
- Installer checks and installs WebView2 Runtime automatically when missing.

## Local Development

### Prerequisites

- Python 3.11+
- `uv` (recommended)

### Install

```bash
uv sync --extra dev
```

### Run

```bash
uv run python main.py
```

Debug mode:

```bash
DEEPREAD_DEBUG=true uv run python main.py
```

### Tests

```bash
uv run pytest -q
```

## Windows Packaging

Local Windows build command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -Version 0.1.0
```

This will:

- prefetch OCR models into `build_assets/models`
- build `dist/BetterPDF` with PyInstaller
- create `BetterPDF-portable.bat` for portable mode

To generate installer (`.exe`), compile `installer/BetterPDF.iss` with Inno Setup.

## GitHub Actions Release

Workflow file: `.github/workflows/release-windows.yml`

Trigger release by pushing a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow will automatically:

- build Windows x64 app
- create setup + portable artifacts
- generate `SHA256SUMS.txt`
- publish assets to GitHub Release

## Runtime Environment Variables

- `DEEPREAD_OCR_MODEL_DIR`: Override OCR model root
- `DEEPREAD_PORTABLE_MODE=1`: Store app data near executable
- `DEEPREAD_PORTABLE_DIR`: Custom portable data directory
- `DEEPREAD_DEBUG=true`: Enable webview debug mode

## License

MIT License - see `LICENSE`.
