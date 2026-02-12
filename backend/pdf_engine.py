"""
PDF Engine using PyMuPDF for rendering and text extraction.
"""

import base64
import fitz  # PyMuPDF
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image


class PDFEngine:
    """
    PDF rendering and text extraction engine using PyMuPDF.

    Features:
    - Render pages to images (PNG) with configurable zoom
    - Extract text from pages or specific regions
    - Cache rendered pages for performance
    - Get page dimensions and metadata
    """

    def __init__(self, file_path: str):
        """
        Initialize the PDF engine with a file path.

        Args:
            file_path: Path to the PDF file
        """
        self.file_path = file_path
        self.doc = fitz.open(file_path)
        self.page_count = len(self.doc)
        self._cache: dict[tuple[int, float], str] = {}  # (page_num, zoom) -> base64_image
        self._page_sizes: dict[int, tuple[float, float]] = {}  # page_num -> (width, height)

    def get_metadata(self) -> dict:
        """Get PDF metadata."""
        return {
            "file_name": Path(self.file_path).name,
            "page_count": self.page_count,
            "title": self.doc.metadata.get("title", ""),
            "author": self.doc.metadata.get("author", ""),
            "subject": self.doc.metadata.get("subject", ""),
        }

    def render_page(self, page_num: int, zoom: float = 1.0) -> str:
        """
        Render a page to a base64-encoded PNG image.

        Args:
            page_num: 1-based page number
            zoom: Zoom factor (1.0 = 100%, 2.0 = 200%)

        Returns:
            Base64-encoded PNG image string (without data URI prefix)
        """
        cache_key = (page_num, round(zoom, 2))
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Validate page number
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        # Get page (0-indexed in PyMuPDF)
        page = self.doc[page_num - 1]

        # Create transformation matrix for zoom
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        img_str = base64.b64encode(buffer.getvalue()).decode()

        # Cache the result
        self._cache[cache_key] = img_str

        return img_str

    def extract_text(self, page_num: int, rect: Optional[dict] = None) -> str:
        """
        Extract text from a page or specific region.

        Args:
            page_num: 1-based page number
            rect: Optional rectangle dict with keys: x1, y1, x2, y2
                  If None, extracts all text from the page

        Returns:
            Extracted text string
        """
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        page = self.doc[page_num - 1]

        if rect:
            # Extract text from specific rectangle
            fitz_rect = fitz.Rect(rect["x1"], rect["y1"], rect["x2"], rect["y2"])
            return page.get_text("text", clip=fitz_rect)
        else:
            # Extract all text from page
            return page.get_text("text")

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """
        Get the dimensions of a page.

        Args:
            page_num: 1-based page number

        Returns:
            Tuple of (width, height) in points
        """
        if page_num in self._page_sizes:
            return self._page_sizes[page_num]

        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        page = self.doc[page_num - 1]
        size = (page.rect.width, page.rect.height)
        self._page_sizes[page_num] = size
        return size

    def search_text(self, query: str, page_num: Optional[int] = None) -> list:
        """
        Search for text in the PDF.

        Args:
            query: Search query string
            page_num: Optional page to search (1-based). If None, searches all pages.

        Returns:
            List of search results with page numbers and rectangles
        """
        results = []

        pages_to_search = [page_num] if page_num else range(1, self.page_count + 1)

        for pn in pages_to_search:
            page = self.doc[pn - 1]
            text_instances = page.search_for(query)

            for rect in text_instances:
                results.append({
                    "page": pn,
                    "rect": {
                        "x1": rect.x0,
                        "y1": rect.y0,
                        "x2": rect.x1,
                        "y2": rect.y1,
                    }
                })

        return results

    def close(self):
        """Close the PDF document and free resources."""
        self._cache.clear()
        self._page_sizes.clear()
        self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
