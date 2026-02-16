#!/usr/bin/env python3
"""Prefetch PaddleOCR models into a deterministic local cache for packaging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.ocr.engine import Engine

REQUIRED_MODELS = (
    "PP-OCRv5_mobile_det",
    "PP-OCRv5_mobile_rec",
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_model_files(model_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for file_path in sorted(model_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(model_dir)).replace("\\", "/")
        entries.append(
            {
                "path": rel,
                "size": file_path.stat().st_size,
                "sha256": sha256_of(file_path),
            }
        )
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="build_assets/models",
        help="Model cache root. official_models/ will be created under this path.",
    )
    parser.add_argument(
        "--model-source",
        default="BOS",
        help="Paddle model source (default: BOS).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["PADDLE_PDX_CACHE_HOME"] = str(output_dir)
    os.environ["DEEPREAD_OCR_MODEL_DIR"] = str(output_dir)
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", args.model_source)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    print(f"[prefetch] cache root: {output_dir}")
    print(f"[prefetch] model source: {os.environ.get('PADDLE_PDX_MODEL_SOURCE')}")

    # Trigger PaddleOCR model resolution/download once.
    engine = Engine()
    _ = engine.ocr_model

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache_root": str(output_dir),
        "model_source": os.environ.get("PADDLE_PDX_MODEL_SOURCE", ""),
        "models": [],
    }

    missing: list[str] = []
    for model_name in REQUIRED_MODELS:
        model_dir = output_dir / "official_models" / model_name
        inference_json = model_dir / "inference.json"
        if not inference_json.exists():
            missing.append(model_name)
            continue

        files = collect_model_files(model_dir)
        manifest["models"].append(
            {
                "name": model_name,
                "path": str(model_dir.relative_to(output_dir)).replace("\\", "/"),
                "file_count": len(files),
                "files": files,
            }
        )

    if missing:
        print(f"[prefetch] missing required models: {', '.join(missing)}", file=sys.stderr)
        return 1

    manifest_path = output_dir / "MODEL_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[prefetch] manifest written: {manifest_path}")
    print("[prefetch] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
