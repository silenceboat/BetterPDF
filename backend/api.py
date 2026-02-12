"""
PyWebView API Bridge - Exposes Python backend to JavaScript frontend.
"""

import json
import os
from pathlib import Path
from typing import Optional

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

    def select_pdf_file(self) -> dict:
        """
        Open a file dialog to select a PDF file.

        Returns:
            Dict with selected file path or cancel status
        """
        try:
            import tkinter as tk
            from tkinter import filedialog

            # Create hidden root window
            root = tk.Tk()
            root.withdraw()

            file_path = filedialog.askopenfilename(
                title="Open PDF",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            )

            root.destroy()

            if file_path:
                return {"success": True, "file_path": file_path}
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
