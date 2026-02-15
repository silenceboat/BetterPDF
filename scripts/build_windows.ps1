param(
    [string]$Version = "0.0.0-local",
    [switch]$SkipTests = $false
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = (Join-Path $RepoRoot ".uv-cache")
}

Write-Host "[build] repo root: $RepoRoot"
Write-Host "[build] version: $Version"

uv sync --extra dev --extra build

Write-Host "[build] prefetch OCR models"
if (Test-Path "build_assets/models") {
    Remove-Item "build_assets/models" -Recurse -Force
}
uv run python scripts/prefetch_ocr_models.py --output-dir build_assets/models

if (-not $SkipTests) {
    Write-Host "[build] running focused tests"
    uv run pytest -q tests/test_ocr_engine.py tests/test_ocr_normalize.py tests/test_api_persistence.py
}

Write-Host "[build] running PyInstaller"
uv run pyinstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name BetterPDF `
    --add-data "frontend;frontend" `
    --add-data "backend;backend" `
    --add-data "build_assets/models;models" `
    --collect-submodules paddleocr `
    --collect-submodules paddlex `
    --collect-submodules paddle `
    --collect-submodules webview `
    --collect-data paddleocr `
    --collect-data paddlex `
    --collect-data paddle `
    --collect-data webview `
    main.py

$portableLauncher = @"
@echo off
set DEEPREAD_PORTABLE_MODE=1
"%~dp0BetterPDF.exe" %*
"@
Set-Content -Path (Join-Path $RepoRoot "dist/BetterPDF/BetterPDF-portable.bat") -Value $portableLauncher -Encoding ASCII

Write-Host "[build] completed: dist/BetterPDF"
