"""
Local persistence layer for DeepRead.

Stores per-document session state, recent files, and page notes in SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(file_path: str) -> str:
    return os.path.abspath(os.path.expanduser(file_path))


def _default_data_dir(app_name: str) -> Path:
    home = Path.home()
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(home / "AppData" / "Roaming")))
        return base / app_name
    if os.name == "posix" and "darwin" in os.uname().sysname.lower():
        return home / "Library" / "Application Support" / app_name
    return home / ".local" / "share" / app_name


class PersistenceStore:
    """SQLite-backed persistence for recent files and page notes."""

    def __init__(self, db_path: Optional[str] = None, app_name: str = "DeepRead"):
        data_dir = _default_data_dir(app_name)
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = data_dir / "deepread.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._migrate()

    def close(self):
        with self._lock:
            self._conn.close()

    def _migrate(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    file_path TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    last_opened_at TEXT NOT NULL,
                    last_page INTEGER NOT NULL DEFAULT 1,
                    last_zoom REAL NOT NULL DEFAULT 1.0,
                    ocr_enabled INTEGER NOT NULL DEFAULT 0,
                    ocr_mode TEXT NOT NULL DEFAULT 'page'
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS page_notes (
                    note_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    quote TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    rect_pdf_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_notes_file_page ON page_notes(file_path, page)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_notes_file_updated ON page_notes(file_path, updated_at DESC)"
            )

            self._ensure_columns(
                "documents",
                {
                    "last_page": "INTEGER NOT NULL DEFAULT 1",
                    "last_zoom": "REAL NOT NULL DEFAULT 1.0",
                    "ocr_enabled": "INTEGER NOT NULL DEFAULT 0",
                    "ocr_mode": "TEXT NOT NULL DEFAULT 'page'",
                },
                cur,
            )
            self._ensure_columns(
                "page_notes",
                {
                    "file_path": "TEXT NOT NULL DEFAULT ''",
                    "page": "INTEGER NOT NULL DEFAULT 1",
                    "quote": "TEXT NOT NULL DEFAULT ''",
                    "note": "TEXT NOT NULL DEFAULT ''",
                    "rect_pdf_json": "TEXT NOT NULL DEFAULT '{}'",
                    "created_at": "TEXT NOT NULL DEFAULT ''",
                    "updated_at": "TEXT NOT NULL DEFAULT ''",
                },
                cur,
            )
            self._conn.commit()

    @staticmethod
    def _ensure_columns(table_name: str, required: dict[str, str], cur: sqlite3.Cursor):
        existing = {
            row["name"]
            for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column, definition in required.items():
            if column in existing:
                continue
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {definition}")

    def record_document_opened(self, file_path: str, file_name: str):
        path = _normalize_path(file_path)
        now = _utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO documents (
                    file_path, file_name, last_opened_at, last_page, last_zoom, ocr_enabled, ocr_mode
                )
                VALUES (?, ?, ?, 1, 1.0, 0, 'page')
                ON CONFLICT(file_path) DO UPDATE SET
                    file_name = excluded.file_name,
                    last_opened_at = excluded.last_opened_at
                """,
                (path, file_name, now),
            )
            self._conn.commit()

    def save_session_state(
        self,
        file_path: str,
        last_page: int,
        last_zoom: float,
        ocr_enabled: bool,
        ocr_mode: str,
    ):
        path = _normalize_path(file_path)
        now = _utc_now_iso()
        safe_page = max(1, int(last_page or 1))
        safe_zoom = float(last_zoom or 1.0)
        safe_mode = "document" if ocr_mode == "document" else "page"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO documents (
                    file_path, file_name, last_opened_at, last_page, last_zoom, ocr_enabled, ocr_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_name = excluded.file_name,
                    last_opened_at = excluded.last_opened_at,
                    last_page = excluded.last_page,
                    last_zoom = excluded.last_zoom,
                    ocr_enabled = excluded.ocr_enabled,
                    ocr_mode = excluded.ocr_mode
                """,
                (
                    path,
                    Path(path).name,
                    now,
                    safe_page,
                    safe_zoom,
                    1 if ocr_enabled else 0,
                    safe_mode,
                ),
            )
            self._conn.commit()

    def get_session_state(self, file_path: str) -> dict[str, Any]:
        path = _normalize_path(file_path)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT last_page, last_zoom, ocr_enabled, ocr_mode
                FROM documents
                WHERE file_path = ?
                """,
                (path,),
            ).fetchone()

        if not row:
            return {
                "last_page": 1,
                "last_zoom": 1.0,
                "ocr_enabled": False,
                "ocr_mode": "page",
            }

        return {
            "last_page": max(1, int(row["last_page"] or 1)),
            "last_zoom": float(row["last_zoom"] or 1.0),
            "ocr_enabled": bool(row["ocr_enabled"]),
            "ocr_mode": "document" if row["ocr_mode"] == "document" else "page",
        }

    def get_recent_files(self, limit: int = 20, prune_missing: bool = True) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit or 20))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT file_path, file_name, last_opened_at, last_page
                FROM documents
                ORDER BY last_opened_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        valid_rows: list[dict[str, Any]] = []
        stale_paths: list[str] = []
        for row in rows:
            file_path = row["file_path"]
            if prune_missing and not os.path.exists(file_path):
                stale_paths.append(file_path)
                continue
            valid_rows.append(
                {
                    "file_path": file_path,
                    "file_name": row["file_name"],
                    "last_opened_at": row["last_opened_at"],
                    "last_page": max(1, int(row["last_page"] or 1)),
                }
            )

        if stale_paths:
            with self._lock:
                placeholders = ",".join("?" for _ in stale_paths)
                self._conn.execute(
                    f"DELETE FROM documents WHERE file_path IN ({placeholders})",
                    stale_paths,
                )
                self._conn.execute(
                    f"DELETE FROM page_notes WHERE file_path IN ({placeholders})",
                    stale_paths,
                )
                self._conn.commit()

        return valid_rows

    def list_page_notes(self, file_path: str) -> list[dict[str, Any]]:
        path = _normalize_path(file_path)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT note_id, page, quote, note, rect_pdf_json, created_at, updated_at
                FROM page_notes
                WHERE file_path = ?
                ORDER BY page ASC, updated_at DESC
                """,
                (path,),
            ).fetchall()

        notes: list[dict[str, Any]] = []
        for row in rows:
            try:
                rect_pdf = json.loads(row["rect_pdf_json"] or "{}")
            except Exception:
                rect_pdf = {}
            notes.append(
                {
                    "id": row["note_id"],
                    "page": max(1, int(row["page"] or 1)),
                    "quote": row["quote"] or "",
                    "note": row["note"] or "",
                    "rectPdf": rect_pdf,
                    "createdAt": row["created_at"] or "",
                    "updatedAt": row["updated_at"] or "",
                }
            )
        return notes

    def save_page_notes(self, file_path: str, notes: list[dict[str, Any]]) -> dict[str, int]:
        path = _normalize_path(file_path)
        now = _utc_now_iso()
        safe_notes: list[dict[str, Any]] = []
        for raw in notes or []:
            note_id = str(raw.get("id") or "").strip()
            if not note_id:
                continue
            rect_pdf = raw.get("rectPdf") or raw.get("rect_pdf") or {}
            safe_notes.append(
                {
                    "id": note_id,
                    "page": max(1, int(raw.get("page") or 1)),
                    "quote": str(raw.get("quote") or ""),
                    "note": str(raw.get("note") or ""),
                    "rect_pdf_json": json.dumps(rect_pdf, separators=(",", ":")),
                    "created_at": str(raw.get("createdAt") or raw.get("created_at") or now),
                    "updated_at": str(raw.get("updatedAt") or raw.get("updated_at") or now),
                }
            )

        with self._lock:
            if safe_notes:
                note_ids = [item["id"] for item in safe_notes]
                placeholders = ",".join("?" for _ in note_ids)
                self._conn.execute(
                    f"DELETE FROM page_notes WHERE file_path = ? AND note_id NOT IN ({placeholders})",
                    [path, *note_ids],
                )
            else:
                self._conn.execute("DELETE FROM page_notes WHERE file_path = ?", (path,))

            for item in safe_notes:
                self._conn.execute(
                    """
                    INSERT INTO page_notes (
                        note_id, file_path, page, quote, note, rect_pdf_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(note_id) DO UPDATE SET
                        file_path = excluded.file_path,
                        page = excluded.page,
                        quote = excluded.quote,
                        note = excluded.note,
                        rect_pdf_json = excluded.rect_pdf_json,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item["id"],
                        path,
                        item["page"],
                        item["quote"],
                        item["note"],
                        item["rect_pdf_json"],
                        item["created_at"],
                        item["updated_at"],
                    ),
                )
            self._conn.commit()

        return {"saved": len(safe_notes)}

    def delete_page_note(self, file_path: str, note_id: str):
        path = _normalize_path(file_path)
        nid = str(note_id or "").strip()
        if not nid:
            return
        with self._lock:
            self._conn.execute(
                "DELETE FROM page_notes WHERE file_path = ? AND note_id = ?",
                (path, nid),
            )
            self._conn.commit()

    def save_ai_settings(
        self,
        *,
        base_url: str,
        api_key: str,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
    ):
        payload = {
            "base_url": str(base_url or "").strip().rstrip("/"),
            "api_key": str(api_key or "").strip(),
            "provider": "ollama" if provider == "ollama" else "openai",
            "model": str(model or "").strip() or "gpt-4o-mini",
        }
        now = _utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value, updated_at)
                VALUES ('ai_settings', ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(payload, separators=(",", ":")), now),
            )
            self._conn.commit()

    def get_ai_settings(self) -> dict[str, Any]:
        default_settings = {
            "base_url": "",
            "api_key": "",
            "provider": "openai",
            "model": "gpt-4o-mini",
        }
        with self._lock:
            row = self._conn.execute(
                """
                SELECT setting_value
                FROM app_settings
                WHERE setting_key = 'ai_settings'
                """,
            ).fetchone()

        if not row:
            return default_settings

        try:
            payload = json.loads(row["setting_value"] or "{}")
        except Exception:
            payload = {}

        return {
            "base_url": str(payload.get("base_url") or "").strip().rstrip("/"),
            "api_key": str(payload.get("api_key") or "").strip(),
            "provider": "ollama" if payload.get("provider") == "ollama" else "openai",
            "model": str(payload.get("model") or "").strip() or "gpt-4o-mini",
        }
