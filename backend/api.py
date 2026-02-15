"""
PyWebView API Bridge - Exposes Python backend to JavaScript frontend.
"""

import os
import tempfile
import shutil
from typing import Optional
import subprocess
import threading
import time

from .pdf_engine import PDFEngine
from .ai_service import AIService
from .persistence import PersistenceStore


class DeepReadAPI:
    """
    API class exposed to JavaScript via PyWebView.

    All public methods are callable from JavaScript via pywebview.api.method_name()
    """

    def __init__(self):
        """Initialize the API bridge."""
        self.pdf_engine: Optional[PDFEngine] = None
        self.ai_service = AIService()
        self.current_pdf_path: Optional[str] = None
        self.notes: dict[str, dict] = {}  # note_id -> note data
        self.current_note_id: Optional[str] = None
        self._window = None

        # OCR state
        self._ocr_pipeline = None
        self._ocr_cache: dict = {}  # page_num -> simplified lines
        self._ocr_temp_dir: Optional[str] = None
        self._ocr_job_id = 0
        self._ocr_progress_lock = threading.Lock()
        self._ocr_progress = {
            "status": "idle",  # idle | running | completed | error
            "stage": "idle",   # idle | loading_model | ocr_pages | completed | error
            "job_id": 0,
            "processed_pages": 0,
            "total_pages": 0,
            "total_lines": 0,
            "error": "",
        }

        # Local persistence (session state, recent files, page notes)
        self._persistence: Optional[PersistenceStore] = None
        self._persistence_error: Optional[str] = None
        try:
            self._persistence = PersistenceStore(db_path=os.getenv("DEEPREAD_DB_PATH"))
            stored_ai = self._persistence.get_ai_settings()
            self.ai_service.configure(
                provider=stored_ai.get("provider"),
                model=stored_ai.get("model"),
                base_url=stored_ai.get("base_url"),
                api_key=stored_ai.get("api_key"),
            )
        except Exception as e:
            self._persistence_error = str(e)

    @staticmethod
    def _normalize_file_path(file_path: str) -> str:
        return os.path.abspath(os.path.expanduser(file_path))

    # ==================== PDF Operations ====================

    def open_pdf(self, file_path: str) -> dict:
        """
        Open a PDF file and return metadata.

        Args:
            file_path: Absolute path to the PDF file

        Returns:
            Dict with success status, page count, and metadata
        """
        try:
            normalized_path = self._normalize_file_path(file_path)

            # Close existing PDF if any
            if self.pdf_engine:
                self.pdf_engine.close()
                self._cleanup_ocr()

            self.pdf_engine = PDFEngine(normalized_path)
            self.current_pdf_path = normalized_path

            metadata = self.pdf_engine.get_metadata()
            session_state = {
                "last_page": 1,
                "last_zoom": 1.0,
                "ocr_enabled": False,
                "ocr_mode": "page",
            }
            page_notes: list[dict] = []

            if self._persistence:
                self._persistence.record_document_opened(
                    normalized_path,
                    metadata.get("file_name") or os.path.basename(normalized_path),
                )
                session_state = self._persistence.get_session_state(normalized_path)
                page_notes = self._persistence.list_page_notes(normalized_path)

            return {
                "success": True,
                "file_path": normalized_path,
                "page_count": metadata["page_count"],
                "file_name": metadata["file_name"],
                "title": metadata.get("title", ""),
                "metadata": metadata,
                "session_state": session_state,
                "page_notes": page_notes,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_page(self, page_num: int, zoom: float = 1.0) -> dict:
        """
        Get a page as base64-encoded PNG.

        Args:
            page_num: 1-based page number
            zoom: Zoom factor (1.0 = 100%)

        Returns:
            Dict with success status and base64 image data
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        try:
            image_data = self.pdf_engine.render_page(page_num, zoom)
            page_size = self.pdf_engine.get_page_size(page_num)

            return {
                "success": True,
                "image_data": image_data,
                "page_num": page_num,
                "page_width": page_size[0],
                "page_height": page_size[1],
                "zoom": zoom,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_text(self, page_num: int, rect: Optional[dict] = None) -> dict:
        """
        Extract text from a page or rectangular region.

        Args:
            page_num: 1-based page number
            rect: Optional rectangle {x1, y1, x2, y2}

        Returns:
            Dict with success status and extracted text
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        try:
            text = self.pdf_engine.extract_text(page_num, rect)
            return {
                "success": True,
                "text": text,
                "page_num": page_num,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_pdf(self, query: str, page_num: Optional[int] = None) -> dict:
        """
        Search for text in the PDF.

        Args:
            query: Search string
            page_num: Optional specific page to search

        Returns:
            Dict with search results
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        try:
            results = self.pdf_engine.search_text(query, page_num)
            return {
                "success": True,
                "results": results,
                "query": query,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_pdf_metadata(self) -> dict:
        """Get current PDF metadata."""
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        return {
            "success": True,
            "metadata": self.pdf_engine.get_metadata(),
        }

    def get_recent_files(self, limit: int = 20) -> dict:
        """Return recent files ordered by latest open time."""
        if not self._persistence:
            return {"success": True, "files": []}
        try:
            files = self._persistence.get_recent_files(limit=limit, prune_missing=True)
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_session_state(self, file_path: str, state: Optional[dict] = None) -> dict:
        """
        Persist the current document view state.

        Args:
            file_path: Document path (falls back to current_pdf_path when empty)
            state: Dict with last_page, last_zoom, ocr_enabled, ocr_mode
        """
        if not self._persistence:
            return {"success": False, "error": self._persistence_error or "Persistence unavailable"}

        try:
            target_path = file_path or self.current_pdf_path
            if not target_path:
                return {"success": False, "error": "No PDF path provided"}

            payload = state or {}
            last_page = int(payload.get("last_page") or payload.get("page") or 1)
            last_zoom = float(payload.get("last_zoom") or payload.get("zoom") or 1.0)
            if "ocr_enabled" in payload:
                ocr_enabled = bool(payload.get("ocr_enabled"))
            else:
                ocr_enabled = bool(payload.get("ocrEnabled", False))
            ocr_mode = payload.get("ocr_mode") or payload.get("ocrMode") or "page"

            self._persistence.save_session_state(
                target_path,
                last_page=last_page,
                last_zoom=last_zoom,
                ocr_enabled=ocr_enabled,
                ocr_mode=str(ocr_mode),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_page_notes(self, file_path: str, notes: Optional[list] = None) -> dict:
        """
        Persist all page notes for a document.

        Args:
            file_path: Document path (falls back to current_pdf_path when empty)
            notes: Full note list for the document
        """
        if not self._persistence:
            return {"success": False, "error": self._persistence_error or "Persistence unavailable"}

        try:
            target_path = file_path or self.current_pdf_path
            if not target_path:
                return {"success": False, "error": "No PDF path provided"}
            stats = self._persistence.save_page_notes(target_path, notes or [])
            return {"success": True, **stats}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_page_note(self, file_path: str, note_id: str) -> dict:
        """Delete a single page note for a document."""
        if not self._persistence:
            return {"success": False, "error": self._persistence_error or "Persistence unavailable"}

        try:
            target_path = file_path or self.current_pdf_path
            if not target_path:
                return {"success": False, "error": "No PDF path provided"}
            self._persistence.delete_page_note(target_path, note_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== OCR Operations ====================

    def _cleanup_ocr(self):
        """Clean up OCR pipeline, cache, and temp directory."""
        self._ocr_job_id += 1
        self._ocr_pipeline = None
        self._ocr_cache = {}
        if self._ocr_temp_dir and os.path.exists(self._ocr_temp_dir):
            shutil.rmtree(self._ocr_temp_dir, ignore_errors=True)
            self._ocr_temp_dir = None
        with self._ocr_progress_lock:
            self._ocr_progress = {
                "status": "idle",
                "stage": "idle",
                "job_id": self._ocr_job_id,
                "processed_pages": 0,
                "total_pages": 0,
                "total_lines": 0,
                "error": "",
            }

    def _ensure_ocr_pipeline(self):
        """Lazy-init OCR pipeline."""
        if self._ocr_pipeline is not None:
            return

        from .ocr.pipeline import OCRPipeline
        self._ocr_temp_dir = tempfile.mkdtemp(prefix="deepread_ocr_")
        self._ocr_pipeline = OCRPipeline(self.current_pdf_path, self._ocr_temp_dir)

    def _simplify_ocr_lines(self, page_lines: list[dict]) -> list[dict]:
        """Convert polygon bboxes to {x, y, width, height} rectangles."""
        simplified: list[dict] = []
        for line in page_lines:
            bbox = line["bbox"]  # list of [x, y] polygon vertices
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            x_min = min(xs)
            y_min = min(ys)
            x_max = max(xs)
            y_max = max(ys)
            simplified.append({
                "text": line["text"],
                "confidence": line["confidence"],
                "x": x_min,
                "y": y_min,
                "width": x_max - x_min,
                "height": y_max - y_min,
            })
        return simplified

    def _update_ocr_progress(self, **kwargs):
        with self._ocr_progress_lock:
            self._ocr_progress.update(kwargs)

    def _get_ocr_progress_snapshot(self) -> dict:
        with self._ocr_progress_lock:
            progress = dict(self._ocr_progress)
        total_pages = int(progress.get("total_pages") or 0)
        processed_pages = int(progress.get("processed_pages") or 0)
        progress["percent"] = (
            100.0 * processed_pages / total_pages if total_pages > 0 else 0.0
        )
        return progress

    def _run_ocr_document_job(self, job_id: int, total_pages: int):
        """
        Background worker for full-document OCR with progress updates.
        """
        try:
            total_lines = 0

            # Count existing cached lines as progress baseline.
            processed_pages = 0
            for page_num in range(1, total_pages + 1):
                if page_num in self._ocr_cache:
                    processed_pages += 1
                    total_lines += len(self._ocr_cache[page_num])

            self._update_ocr_progress(
                status="running",
                stage="loading_model",
                job_id=job_id,
                processed_pages=processed_pages,
                total_pages=total_pages,
                total_lines=total_lines,
                error="",
            )

            # May take several minutes on first run (model download + init).
            self._ensure_ocr_pipeline()
            self._update_ocr_progress(stage="ocr_pages")

            for page_num in range(1, total_pages + 1):
                # If a new PDF is opened, cancel this stale job.
                if job_id != self._ocr_job_id:
                    return

                if page_num in self._ocr_cache:
                    continue

                results = self._ocr_pipeline.run(first_page=page_num, last_page=page_num)
                page_lines = results[0] if results else []
                simplified = self._simplify_ocr_lines(page_lines)
                self._ocr_cache[page_num] = simplified

                processed_pages += 1
                total_lines += len(simplified)
                self._update_ocr_progress(
                    status="running",
                    job_id=job_id,
                    processed_pages=processed_pages,
                    total_pages=total_pages,
                    total_lines=total_lines,
                    error="",
                )

            if job_id == self._ocr_job_id:
                self._update_ocr_progress(
                    status="completed",
                    stage="completed",
                    job_id=job_id,
                    processed_pages=total_pages,
                    total_pages=total_pages,
                    total_lines=total_lines,
                    error="",
                )
        except Exception as e:
            if job_id == self._ocr_job_id:
                self._update_ocr_progress(
                    status="error",
                    stage="error",
                    job_id=job_id,
                    error=str(e),
                )

    def ocr_page(self, page_num: int) -> dict:
        """
        Run OCR on a single page and return text lines with bounding boxes.

        Args:
            page_num: 1-based page number

        Returns:
            Dict with success status and list of text lines with bbox info.
            Each line has: text, confidence, x, y, width, height (in PDF points,
            Y=0 at page bottom).
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        try:
            # Return cached result if available
            if page_num in self._ocr_cache:
                return {"success": True, "lines": self._ocr_cache[page_num]}

            self._ensure_ocr_pipeline()

            # Run OCR on the single page
            results = self._ocr_pipeline.run(
                first_page=page_num, last_page=page_num
            )

            # results is list[list[dict]], one entry per page
            page_lines = results[0] if results else []

            simplified = self._simplify_ocr_lines(page_lines)

            # Cache and return
            self._ocr_cache[page_num] = simplified
            return {"success": True, "lines": simplified}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def ocr_document(self) -> dict:
        """
        Run OCR for the whole document and cache all pages.

        Returns:
            Dict with success status, processed page count, and total lines.
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        page_count = self.pdf_engine.page_count
        if page_count <= 0:
            return {"success": True, "page_count": 0, "total_lines": 0}

        start = self.start_ocr_document()
        if not start.get("success"):
            return start

        # Keep compatibility for callers expecting synchronous behavior.
        # Poll until current job finishes.
        while True:
            progress = self.get_ocr_progress()
            status = progress.get("status")
            if status == "completed":
                return {
                    "success": True,
                    "page_count": progress.get("total_pages", page_count),
                    "total_lines": progress.get("total_lines", 0),
                    "cached": start.get("cached", False),
                }
            if status == "error":
                return {"success": False, "error": progress.get("error", "OCR failed")}
            time.sleep(0.1)

    def start_ocr_document(self) -> dict:
        """
        Start full-document OCR in background and return immediately.
        """
        if not self.pdf_engine:
            return {"success": False, "error": "No PDF open"}

        page_count = self.pdf_engine.page_count
        if page_count <= 0:
            self._update_ocr_progress(
                status="completed",
                stage="completed",
                processed_pages=0,
                total_pages=0,
                total_lines=0,
                error="",
            )
            return {"success": True, "started": False, "cached": True, "total_pages": 0}

        # If OCR already running for current job, return status.
        progress = self._get_ocr_progress_snapshot()
        if progress.get("status") == "running":
            return {
                "success": True,
                "started": False,
                "already_running": True,
                "total_pages": progress.get("total_pages", page_count),
            }

        # If fully cached, mark completed and skip worker thread.
        if len(self._ocr_cache) >= page_count:
            total_lines = sum(len(lines) for lines in self._ocr_cache.values())
            self._update_ocr_progress(
                status="completed",
                stage="completed",
                processed_pages=page_count,
                total_pages=page_count,
                total_lines=total_lines,
                error="",
            )
            return {
                "success": True,
                "started": False,
                "cached": True,
                "total_pages": page_count,
                "total_lines": total_lines,
            }

        job_id = self._ocr_job_id
        self._update_ocr_progress(
            status="running",
            stage="loading_model",
            job_id=job_id,
            processed_pages=0,
            total_pages=page_count,
            total_lines=0,
            error="",
        )

        thread = threading.Thread(
            target=self._run_ocr_document_job,
            args=(job_id, page_count),
            daemon=True,
        )
        thread.start()
        return {
            "success": True,
            "started": True,
            "cached": False,
            "total_pages": page_count,
        }

    def get_ocr_progress(self) -> dict:
        """
        Get current background OCR progress.
        """
        progress = self._get_ocr_progress_snapshot()
        progress["success"] = True
        return progress

    # ==================== AI Operations ====================

    def ai_chat(self, message: str, context: str = "") -> dict:
        """
        Send a chat message to the AI.

        Args:
            message: User message
            context: Optional context (e.g., selected text)

        Returns:
            Dict with success status and AI response
        """
        try:
            response = self.ai_service.chat(message, context if context else None)
            return {
                "success": True,
                "response": response,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_ai_settings(self) -> dict:
        """Return active AI provider settings."""
        try:
            if self._persistence:
                settings = self._persistence.get_ai_settings()
                self.ai_service.configure(
                    provider=settings.get("provider"),
                    model=settings.get("model"),
                    base_url=settings.get("base_url"),
                    api_key=settings.get("api_key"),
                )
            settings = self.ai_service.get_config()
            return {"success": True, "settings": settings}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_ai_settings(self, settings: Optional[dict] = None) -> dict:
        """Persist and apply AI provider settings."""
        try:
            payload = settings or {}
            provider = payload.get("provider") or "openai"
            base_url = str(payload.get("base_url") or payload.get("baseUrl") or "").strip().rstrip("/")
            api_key = str(payload.get("api_key") or payload.get("apiKey") or "").strip()
            model = str(payload.get("model") or "").strip() or None

            if provider == "openai" and not api_key and not os.getenv("OPENAI_API_KEY"):
                return {"success": False, "error": "API Key is required for OpenAI-compatible providers"}

            self.ai_service.configure(
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )

            if self._persistence:
                current = self.ai_service.get_config()
                self._persistence.save_ai_settings(
                    base_url=current.get("base_url", ""),
                    api_key=current.get("api_key", ""),
                    provider=current.get("provider", "openai"),
                    model=current.get("model", "gpt-4o-mini"),
                )

            return {"success": True, "settings": self.ai_service.get_config()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ai_action(self, action: str, selected_text: str) -> dict:
        """
        Perform an AI action on selected text.

        Args:
            action: Action type (explain, summarize, translate, define)
            selected_text: Text to process

        Returns:
            Dict with success status and AI response
        """
        try:
            response = self.ai_service.ai_action(action, selected_text)
            return {
                "success": True,
                "response": response,
                "action": action,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def ai_quick_action(self, action_type: str, document_context: str = "") -> dict:
        """
        Perform a quick action on the document.

        Args:
            action_type: Type of action (full_summary, key_points, questions)
            document_context: Context about the document

        Returns:
            Dict with success status and AI response
        """
        try:
            response = self.ai_service.quick_action(action_type, document_context)
            return {
                "success": True,
                "response": response,
                "action_type": action_type,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== Note Operations ====================

    def save_note(self, note_id: str, title: str, content: str) -> dict:
        """
        Save a note.

        Args:
            note_id: Note ID (empty string for new note)
            title: Note title
            content: Note content (markdown)

        Returns:
            Dict with success status and note_id
        """
        try:
            # Generate new ID if needed
            if not note_id:
                import uuid
                note_id = str(uuid.uuid4())[:8]

            self.notes[note_id] = {
                "id": note_id,
                "title": title,
                "content": content,
                "created_at": self._get_timestamp(),
                "updated_at": self._get_timestamp(),
            }

            self.current_note_id = note_id

            return {
                "success": True,
                "note_id": note_id,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def load_note(self, note_id: str) -> dict:
        """
        Load a note by ID.

        Args:
            note_id: Note ID to load

        Returns:
            Dict with note data
        """
        if note_id not in self.notes:
            return {"success": False, "error": "Note not found"}

        self.current_note_id = note_id
        return {
            "success": True,
            "note": self.notes[note_id],
        }

    def list_notes(self) -> dict:
        """
        List all saved notes.

        Returns:
            Dict with list of notes
        """
        return {
            "success": True,
            "notes": list(self.notes.values()),
        }

    def delete_note(self, note_id: str) -> dict:
        """
        Delete a note.

        Args:
            note_id: Note ID to delete

        Returns:
            Dict with success status
        """
        if note_id in self.notes:
            del self.notes[note_id]
            if self.current_note_id == note_id:
                self.current_note_id = None

        return {"success": True}

    # ==================== Utility Operations ====================

    def _select_pdf_file_windows(self) -> dict:
        """
        Select a PDF file on Windows using a separate PowerShell process.

        This avoids pywebview/WinForms cross-thread dialog issues that can
        freeze the app when called from JS API worker threads.
        """
        script = r"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = "PDF Files (*.pdf)|*.pdf|All Files (*.*)|*.*"
$dialog.Multiselect = $false
$dialog.RestoreDirectory = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    Write-Output $dialog.FileName
}
"""
        shell_cmds = [
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            ["pwsh", "-NoProfile", "-Command", script],
        ]

        def _decode_output(data: bytes) -> str:
            for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16le"):
                try:
                    return data.decode(enc).strip()
                except Exception:
                    continue
            return data.decode(errors="replace").strip()

        last_error: Optional[str] = None
        for cmd in shell_cmds:
            try:
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    timeout=120,
                )
            except FileNotFoundError:
                last_error = f"Command not found: {cmd[0]}"
                continue
            except Exception as e:
                last_error = str(e)
                continue

            if completed.returncode != 0:
                stderr = _decode_output(completed.stderr or b"")
                last_error = stderr or f"{cmd[0]} exited with code {completed.returncode}"
                continue

            file_path = _decode_output(completed.stdout or b"")
            if file_path:
                return {"success": True, "file_path": file_path}
            return {"success": False, "cancelled": True}

        return {
            "success": False,
            "error": f"Failed to open file dialog on Windows. {last_error or ''}".strip(),
        }

    def select_pdf_file(self) -> dict:
        """
        Open a file dialog to select a PDF file.

        Uses a Windows-specific PowerShell dialog on Win32 to avoid pywebview
        cross-thread deadlocks, and pywebview native dialogs on other platforms.

        Returns:
            Dict with selected file path or cancel status
        """
        try:
            if os.name == "nt":
                return self._select_pdf_file_windows()

            if not self._window:
                return {"success": False, "error": "Window not available"}

            import webview
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('PDF Files (*.pdf)', 'All Files (*.*)'),
            )

            if result and len(result) > 0:
                return {"success": True, "file_path": str(result[0])}
            else:
                return {"success": False, "cancelled": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_app_info(self) -> dict:
        """Get application information."""
        return {
            "name": "DeepRead AI",
            "version": "0.2.0",
            "platform": os.name,
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().isoformat()
