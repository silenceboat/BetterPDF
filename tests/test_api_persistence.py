"""Tests for local persistence integration in DeepReadAPI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import backend.api as api_module
import backend.engine_factory as engine_factory_module
from backend.persistence import PersistenceStore


class FakePDFEngine:
    """Minimal stub for API-level persistence tests."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.page_count = 12

    def close(self):
        return None

    def get_metadata(self) -> dict:
        return {
            "file_name": Path(self.file_path).name,
            "page_count": self.page_count,
            "title": "",
            "author": "",
            "subject": "",
        }


def _make_api(monkeypatch, db_path: Path):
    monkeypatch.setenv("DEEPREAD_DB_PATH", str(db_path))
    monkeypatch.setattr(api_module, "PDFEngine", FakePDFEngine)
    monkeypatch.setattr(engine_factory_module, "PDFEngine", FakePDFEngine)
    return api_module.DeepReadAPI()


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n%stub\n")


def test_recent_files_sorted_and_saved(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    api = _make_api(monkeypatch, db_path)

    file_a = tmp_path / "a.pdf"
    file_b = tmp_path / "b.pdf"
    _touch(file_a)
    _touch(file_b)

    assert api.open_pdf(str(file_a))["success"]
    assert api.open_pdf(str(file_b))["success"]

    recent = api.get_recent_files(limit=20)
    assert recent["success"]
    assert recent["files"][0]["file_path"] == str(file_b.resolve())
    assert recent["files"][1]["file_path"] == str(file_a.resolve())


def test_session_state_restored_after_restart(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    file_path = tmp_path / "restore.pdf"
    _touch(file_path)

    api = _make_api(monkeypatch, db_path)
    assert api.open_pdf(str(file_path))["success"]
    save_result = api.save_session_state(
        str(file_path),
        {
            "last_page": 7,
            "last_zoom": 1.75,
            "ocr_enabled": True,
            "ocr_mode": "document",
        },
    )
    assert save_result["success"]
    if api._persistence:
        api._persistence.close()

    api2 = _make_api(monkeypatch, db_path)
    reopened = api2.open_pdf(str(file_path))
    assert reopened["success"]
    assert reopened["session_state"]["last_page"] == 7
    assert reopened["session_state"]["last_zoom"] == 1.75
    assert reopened["session_state"]["ocr_enabled"] is True
    assert reopened["session_state"]["ocr_mode"] == "document"


def test_page_notes_persist_after_restart(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    file_path = tmp_path / "notes.pdf"
    _touch(file_path)

    notes = [
        {
            "id": "n1",
            "page": 2,
            "quote": "quoted text",
            "note": "my note",
            "rectPdf": {"x1": 10, "y1": 20, "x2": 60, "y2": 70},
            "createdAt": "2026-02-15T10:00:00Z",
            "updatedAt": "2026-02-15T10:05:00Z",
        }
    ]

    api = _make_api(monkeypatch, db_path)
    assert api.open_pdf(str(file_path))["success"]
    save_result = api.save_page_notes(str(file_path), notes)
    assert save_result["success"]
    assert save_result["saved"] == 1
    if api._persistence:
        api._persistence.close()

    api2 = _make_api(monkeypatch, db_path)
    reopened = api2.open_pdf(str(file_path))
    assert reopened["success"]
    assert len(reopened["page_notes"]) == 1
    assert reopened["page_notes"][0]["id"] == "n1"
    assert reopened["page_notes"][0]["note"] == "my note"


def test_ai_settings_persist_after_restart(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    api = _make_api(monkeypatch, db_path)

    save_result = api.save_ai_settings(
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://example.com/v1/",
            "api_key": "sk-test-key",
        }
    )
    assert save_result["success"]
    assert save_result["settings"]["base_url"] == "https://example.com/v1"
    assert save_result["settings"]["api_key"] == "sk-test-key"
    if api._persistence:
        api._persistence.close()

    api2 = _make_api(monkeypatch, db_path)
    loaded = api2.get_ai_settings()
    assert loaded["success"]
    assert loaded["settings"]["provider"] == "openai"
    assert loaded["settings"]["base_url"] == "https://example.com/v1"
    assert loaded["settings"]["api_key"] == "sk-test-key"


def test_anthropic_settings_persist_after_restart(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    api = _make_api(monkeypatch, db_path)

    save_result = api.save_ai_settings(
        {
            "provider": "anthropic",
            "model": "claude-3-5-haiku-latest",
            "base_url": "https://api.anthropic.com/",
            "api_key": "sk-ant-test",
        }
    )
    assert save_result["success"]
    assert save_result["settings"]["provider"] == "anthropic"
    assert save_result["settings"]["base_url"] == "https://api.anthropic.com"
    if api._persistence:
        api._persistence.close()

    api2 = _make_api(monkeypatch, db_path)
    loaded = api2.get_ai_settings()
    assert loaded["success"]
    assert loaded["settings"]["provider"] == "anthropic"
    assert loaded["settings"]["model"] == "claude-3-5-haiku-latest"


def test_save_anthropic_settings_requires_key(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    api = _make_api(monkeypatch, db_path)

    save_result = api.save_ai_settings(
        {
            "provider": "anthropic",
            "model": "claude-3-5-haiku-latest",
            "base_url": "https://api.anthropic.com",
            "api_key": "",
        }
    )
    assert save_result["success"] is False
    assert "API Key is required for Anthropic provider" in save_result["error"]


def test_delete_page_note(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    file_path = tmp_path / "delete.pdf"
    _touch(file_path)

    api = _make_api(monkeypatch, db_path)
    assert api.open_pdf(str(file_path))["success"]
    api.save_page_notes(
        str(file_path),
        [
            {
                "id": "n1",
                "page": 1,
                "quote": "q1",
                "note": "",
                "rectPdf": {"x1": 1, "y1": 1, "x2": 2, "y2": 2},
            },
            {
                "id": "n2",
                "page": 1,
                "quote": "q2",
                "note": "",
                "rectPdf": {"x1": 2, "y1": 2, "x2": 3, "y2": 3},
            },
        ],
    )
    delete_result = api.delete_page_note(str(file_path), "n1")
    assert delete_result["success"]

    reopened = api.open_pdf(str(file_path))
    note_ids = [item["id"] for item in reopened["page_notes"]]
    assert note_ids == ["n2"]


def test_recent_files_prunes_missing_paths(monkeypatch, tmp_path):
    db_path = tmp_path / "deepread.db"
    file_path = tmp_path / "missing.pdf"
    _touch(file_path)

    api = _make_api(monkeypatch, db_path)
    assert api.open_pdf(str(file_path))["success"]
    file_path.unlink()

    recent = api.get_recent_files(limit=20)
    assert recent["success"]
    assert recent["files"] == []


def test_persistence_migrates_legacy_documents_schema(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE documents (
            file_path TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    store = PersistenceStore(db_path=str(db_path))
    store.save_session_state(
        str(tmp_path / "legacy.pdf"),
        last_page=3,
        last_zoom=1.5,
        ocr_enabled=True,
        ocr_mode="document",
    )
    state = store.get_session_state(str(tmp_path / "legacy.pdf"))
    assert state["last_page"] == 3
    assert state["last_zoom"] == 1.5
    assert state["ocr_enabled"] is True
    assert state["ocr_mode"] == "document"


def test_persistence_ai_settings_roundtrip(tmp_path):
    db_path = tmp_path / "settings.db"
    store = PersistenceStore(db_path=str(db_path))

    defaults = store.get_ai_settings()
    assert defaults["provider"] == "openai"
    assert defaults["base_url"] == ""
    assert defaults["api_key"] == ""

    store.save_ai_settings(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://proxy.example.com/v1/",
        api_key="sk-local",
    )
    loaded = store.get_ai_settings()
    assert loaded["provider"] == "openai"
    assert loaded["model"] == "gpt-4o-mini"
    assert loaded["base_url"] == "https://proxy.example.com/v1"
    assert loaded["api_key"] == "sk-local"

    store.save_ai_settings(
        provider="anthropic",
        model="claude-3-5-haiku-latest",
        base_url="https://api.anthropic.com/",
        api_key="sk-ant-local",
    )
    loaded2 = store.get_ai_settings()
    assert loaded2["provider"] == "anthropic"
    assert loaded2["model"] == "claude-3-5-haiku-latest"
    assert loaded2["base_url"] == "https://api.anthropic.com"
    assert loaded2["api_key"] == "sk-ant-local"
