"""
Document Engine Protocol - Abstract interface for document rendering engines.

All engines (PDF, DOCX, TXT) must implement this protocol.
"""

from typing import Protocol, Optional, Tuple


class DocumentEngine(Protocol):
    """
    Protocol defining the interface for document rendering engines.

    All engines must provide:
    - Page-based rendering to PNG images
    - Text extraction and search
    - Metadata access
    - Resource cleanup
    """

    file_path: str
    page_count: int

    def get_metadata(self) -> dict:
        """
        Get document metadata.

        Returns:
            Dictionary with keys: file_name, page_count, title, author, subject
        """
        ...

    def render_page(self, page_num: int, zoom: float = 1.0) -> str:
        """
        Render a page to a base64-encoded PNG image.

        Args:
            page_num: 1-based page number
            zoom: Zoom factor (1.0 = 100%, 2.0 = 200%)

        Returns:
            Base64-encoded PNG image string (without data URI prefix)
        """
        ...

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
        ...

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """
        Get the dimensions of a page.

        Args:
            page_num: 1-based page number

        Returns:
            Tuple of (width, height) in points
        """
        ...

    def search_text(self, query: str, page_num: Optional[int] = None) -> list:
        """
        Search for text in the document.

        Args:
            query: Search query string
            page_num: Optional page to search (1-based). If None, searches all pages.

        Returns:
            List of search results with page numbers and rectangles
        """
        ...

    def close(self):
        """Close the document and free resources."""
        ...
