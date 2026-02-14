"""
PyWebView API Bridge - Exposes Python backend to JavaScript frontend.
"""

import os
import tempfile
import shutil
from typing import Optional
import subprocess

from .pdf_engine import PDFEngine
from .ai_service import AIService


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
            # Close existing PDF if any
            if self.pdf_engine:
                self.pdf_engine.close()
                self._cleanup_ocr()

            self.pdf_engine = PDFEngine(file_path)
            self.current_pdf_path = file_path

            metadata = self.pdf_engine.get_metadata()

            return {
                "success": True,
                "page_count": metadata["page_count"],
                "file_name": metadata["file_name"],
                "title": metadata.get("title", ""),
                "metadata": metadata,
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

    # ==================== OCR Operations ====================

    def _cleanup_ocr(self):
        """Clean up OCR pipeline, cache, and temp directory."""
        self._ocr_pipeline = None
        self._ocr_cache = {}
        if self._ocr_temp_dir and os.path.exists(self._ocr_temp_dir):
            shutil.rmtree(self._ocr_temp_dir, ignore_errors=True)
            self._ocr_temp_dir = None

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

            # Lazy-init the OCR pipeline (import deferred to avoid slow startup)
            if self._ocr_pipeline is None:
                from .ocr.pipeline import OCRPipeline
                self._ocr_temp_dir = tempfile.mkdtemp(prefix="deepread_ocr_")
                self._ocr_pipeline = OCRPipeline(
                    self.current_pdf_path, self._ocr_temp_dir
                )

            # Run OCR on the single page
            results = self._ocr_pipeline.run(
                first_page=page_num, last_page=page_num
            )

            # results is list[list[dict]], one entry per page
            page_lines = results[0] if results else []

            # Simplify polygon bbox to rectangle {x, y, width, height}
            simplified = []
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

            # Cache and return
            self._ocr_cache[page_num] = simplified
            return {"success": True, "lines": simplified}

        except Exception as e:
            return {"success": False, "error": str(e)}

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
