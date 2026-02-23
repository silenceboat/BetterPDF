"""
Text Engine for rendering plain text files as paginated PNG images.
"""

import base64
import platform
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


class TextEngine:
    """
    Text file rendering engine.

    Features:
    - Automatic encoding detection (UTF-8 → GBK → Latin-1)
    - Page-based rendering to PNG images
    - Fixed page size (US Letter: 612×792 points)
    - Chinese font support (Windows: Microsoft YaHei, Linux: system fonts)
    - Text extraction and search
    """

    # Page dimensions (US Letter in points)
    PAGE_WIDTH = 612
    PAGE_HEIGHT = 792

    # Rendering settings
    MARGIN_LEFT = 40
    MARGIN_TOP = 40
    MARGIN_RIGHT = 40
    MARGIN_BOTTOM = 40
    FONT_SIZE = 12
    LINE_HEIGHT = 18  # Font size * 1.5 for comfortable reading
    CHARS_PER_LINE = 80  # Characters per line for text wrapping

    def __init__(self, file_path: str):
        """
        Initialize the text engine with a file path.

        Args:
            file_path: Path to the text file
        """
        self.file_path = file_path
        self._content = self._load_file()
        self._pages = self._paginate_text()
        self.page_count = len(self._pages)
        self._font = self._get_font()
        self._cache: dict[tuple[int, float], str] = {}  # (page_num, zoom) -> base64_image

    def _load_file(self) -> str:
        """
        Load text file with automatic encoding detection.

        Tries UTF-8 → GBK → Latin-1 in order.
        """
        encodings = ['utf-8', 'gbk', 'latin-1']

        for encoding in encodings:
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue

        # Fallback: read with errors replaced
        with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """
        Get appropriate font for the current platform.

        Windows: Microsoft YaHei (msyh.ttc)
        Linux: DejaVu Sans Mono or system Chinese fonts
        """
        system = platform.system()
        font_paths = []

        if system == 'Windows':
            font_paths = [
                'C:/Windows/Fonts/msyh.ttc',  # Microsoft YaHei
                'C:/Windows/Fonts/simhei.ttf',  # SimHei
                'C:/Windows/Fonts/simsun.ttc',  # SimSun
            ]
        elif system == 'Linux':
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
                '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',  # WenQuanYi
                '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            ]
        elif system == 'Darwin':  # macOS
            font_paths = [
                '/System/Library/Fonts/PingFang.ttc',
                '/Library/Fonts/Arial Unicode.ttf',
            ]

        # Try each font path
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, self.FONT_SIZE)
            except (OSError, IOError):
                continue

        # Fallback to default font
        try:
            return ImageFont.truetype("DejaVuSansMono.ttf", self.FONT_SIZE)
        except (OSError, IOError):
            # Use PIL's default font as last resort
            return ImageFont.load_default()

    def _paginate_text(self) -> list[list[str]]:
        """
        Split text into pages.

        Returns:
            List of pages, where each page is a list of lines
        """
        # Calculate lines per page
        usable_height = self.PAGE_HEIGHT - self.MARGIN_TOP - self.MARGIN_BOTTOM
        lines_per_page = int(usable_height / self.LINE_HEIGHT)

        # Wrap long lines
        wrapped_lines = []
        for line in self._content.split('\n'):
            if not line:
                wrapped_lines.append('')
            else:
                # Wrap line to fit page width
                wrapped = textwrap.wrap(
                    line,
                    width=self.CHARS_PER_LINE,
                    break_long_words=True,
                    break_on_hyphens=False,
                    replace_whitespace=False
                )
                if wrapped:
                    wrapped_lines.extend(wrapped)
                else:
                    wrapped_lines.append('')

        # Split into pages
        pages = []
        for i in range(0, len(wrapped_lines), lines_per_page):
            page_lines = wrapped_lines[i:i + lines_per_page]
            pages.append(page_lines)

        # Ensure at least one page
        if not pages:
            pages = [[]]

        return pages

    def get_metadata(self) -> dict:
        """Get text file metadata."""
        return {
            "file_name": Path(self.file_path).name,
            "page_count": self.page_count,
            "title": Path(self.file_path).stem,
            "author": "",
            "subject": "Plain Text Document",
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

        # Get page lines (0-indexed)
        page_lines = self._pages[page_num - 1]

        # Calculate image dimensions with zoom
        img_width = int(self.PAGE_WIDTH * zoom)
        img_height = int(self.PAGE_HEIGHT * zoom)

        # Create white background image
        img = Image.new('RGB', (img_width, img_height), color='white')
        draw = ImageDraw.Draw(img)

        # Scale font size with zoom
        if zoom != 1.0:
            try:
                scaled_font_size = int(self.FONT_SIZE * zoom)
                font = ImageFont.truetype(self._font.path, scaled_font_size)
            except (OSError, IOError, AttributeError):
                font = self._font
        else:
            font = self._font

        # Draw text lines
        y_position = int(self.MARGIN_TOP * zoom)
        x_position = int(self.MARGIN_LEFT * zoom)
        line_height = int(self.LINE_HEIGHT * zoom)

        for line in page_lines:
            draw.text((x_position, y_position), line, fill='black', font=font)
            y_position += line_height

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
            rect: Optional rectangle dict (not implemented for text files)

        Returns:
            Extracted text string
        """
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        page_lines = self._pages[page_num - 1]
        return '\n'.join(page_lines)

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """
        Get the dimensions of a page.

        Args:
            page_num: 1-based page number

        Returns:
            Tuple of (width, height) in points
        """
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        return (self.PAGE_WIDTH, self.PAGE_HEIGHT)

    def search_text(self, query: str, page_num: Optional[int] = None) -> list:
        """
        Search for text in the document.

        Args:
            query: Search query string
            page_num: Optional page to search (1-based). If None, searches all pages.

        Returns:
            List of search results with page numbers and rectangles
        """
        results = []
        pages_to_search = [page_num] if page_num else range(1, self.page_count + 1)

        for pn in pages_to_search:
            page_lines = self._pages[pn - 1]
            page_text = '\n'.join(page_lines)

            # Find all occurrences
            query_lower = query.lower()
            text_lower = page_text.lower()
            start = 0

            while True:
                pos = text_lower.find(query_lower, start)
                if pos == -1:
                    break

                # Calculate line number and position
                lines_before = page_text[:pos].count('\n')
                line_start_pos = page_text.rfind('\n', 0, pos) + 1
                char_position = pos - line_start_pos

                # Calculate approximate rectangle
                y1 = self.MARGIN_TOP + (lines_before * self.LINE_HEIGHT)
                y2 = y1 + self.LINE_HEIGHT
                x1 = self.MARGIN_LEFT + (char_position * (self.FONT_SIZE * 0.6))  # Approximate char width
                x2 = x1 + (len(query) * (self.FONT_SIZE * 0.6))

                results.append({
                    "page": pn,
                    "rect": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    }
                })

                start = pos + 1

        return results

    def close(self):
        """Close the document and free resources."""
        self._cache.clear()
        self._pages.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
