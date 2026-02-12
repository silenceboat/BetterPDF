"""
DeepRead AI - Backend Package

Contains the Python backend logic for the web-based UI:
- PDF Engine (PyMuPDF wrapper)
- AI Service (OpenAI/Ollama integration)
- API Bridge (PyWebView JS API)
"""

from .api import DeepReadAPI
from .pdf_engine import PDFEngine
from .ai_service import AIService

__all__ = ["DeepReadAPI", "PDFEngine", "AIService"]
