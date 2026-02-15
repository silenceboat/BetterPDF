# Windows Release Playbook

## Output Artifacts

- `BetterPDF-<version>-win-x64-setup.exe`
- `BetterPDF-<version>-win-x64-portable.zip`
- `SHA256SUMS.txt`

## GitHub Actions Trigger

Push a tag like `v0.1.0`.

```bash
git tag v0.1.0
git push origin v0.1.0
```

## What the workflow does

1. Prefetch PaddleOCR models (`PP-OCRv5_mobile_det`, `PP-OCRv5_mobile_rec`)
2. Bundle app with PyInstaller (`dist/BetterPDF`)
3. Build installer via Inno Setup
4. Build portable zip and checksums
5. Publish release assets

## Offline OCR guarantee

- Models are stored under `models/official_models/...` in the bundle.
- `main.py` sets `DEEPREAD_OCR_MODEL_DIR` and related Paddle env vars for frozen app.
- `Engine` prefers local bundled models before any network download.

## WebView2 runtime

The installer includes `MicrosoftEdgeWebView2Setup.exe` and runs it silently when runtime is absent.
