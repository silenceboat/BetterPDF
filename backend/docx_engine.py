"""
DOCX Engine for rendering Word documents as paginated PNG images.
"""

import base64
import platform
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


# Style map: style_name_prefix -> (font_size, bold, space_after_px)
STYLE_MAP = {
    "title":     (20, True,  16),
    "heading 1": (18, True,  14),
    "heading 2": (16, True,  12),
    "heading 3": (14, True,  10),
    "subtitle":  (14, False, 12),
    "_default":  (12, False,  8),
}

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_LEFT = 50
MARGIN_TOP = 55
MARGIN_RIGHT = 50
MARGIN_BOTTOM = 55
LINE_HEIGHT_RATIO = 1.4


@dataclass
class _RenderedLine:
    text: str
    y_offset: float  # absolute y position within page
    font_size: int
    bold: bool


@dataclass
class _PageRecord:
    lines: List[_RenderedLine] = field(default_factory=list)
    para_start: int = 0  # inclusive index into _paragraphs
    para_end: int = 0    # exclusive index into _paragraphs


@dataclass
class _ParagraphInfo:
    text: str
    font_size: int
    bold: bool
    space_after: int


class DocxEngine:
    """
    DOCX rendering engine.

    Parses a .docx file with python-docx and renders each page
    as a base64-encoded PNG image using Pillow.
    """

    PAGE_WIDTH = PAGE_WIDTH
    PAGE_HEIGHT = PAGE_HEIGHT

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._paragraphs: List[_ParagraphInfo] = []
        self._page_records: List[_PageRecord] = []
        self._font_cache: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self._render_cache: Dict[Tuple[int, float], str] = {}

        self._load_paragraphs()
        self._load_fonts()
        self._paginate()
        self.page_count = len(self._page_records)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_paragraphs(self):
        """Parse docx paragraphs into _ParagraphInfo list."""
        try:
            import docx  # python-docx
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX support. "
                "Install it with: pip install python-docx"
            )

        doc = docx.Document(self.file_path)
        self._doc = doc

        for para in doc.paragraphs:
            text = para.text
            if not text.strip() and not text:
                # Keep blank lines as paragraph separators
                text = ""

            style_name = (para.style.name if para.style else "") or ""
            style_lower = style_name.lower()

            # Match style prefix against STYLE_MAP
            matched = None
            for key in STYLE_MAP:
                if key == "_default":
                    continue
                if style_lower.startswith(key):
                    matched = STYLE_MAP[key]
                    break
            if matched is None:
                matched = STYLE_MAP["_default"]

            font_size, bold, space_after = matched

            # Paragraph-level bold override: if not heading-bold but all runs are bold
            if not bold and para.runs and all(r.bold for r in para.runs if r.text.strip()):
                bold = True

            self._paragraphs.append(_ParagraphInfo(
                text=text,
                font_size=font_size,
                bold=bold,
                space_after=space_after,
            ))

        # Ensure at least one paragraph so we always have one page
        if not self._paragraphs:
            self._paragraphs.append(_ParagraphInfo(
                text="", font_size=12, bold=False, space_after=8
            ))

    def _load_fonts(self):
        """Pre-load fonts for each (size, bold) combination used in paragraphs."""
        system = platform.system()

        if system == "Windows":
            normal_paths = ["C:/Windows/Fonts/msyh.ttc"]
            bold_paths = [
                "C:/Windows/Fonts/msyhbd.ttc",
                "C:/Windows/Fonts/simhei.ttf",
            ]
        elif system == "Linux":
            normal_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            ]
            bold_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            ]
        else:  # macOS / other
            normal_paths = ["/System/Library/Fonts/PingFang.ttc"]
            bold_paths = ["/System/Library/Fonts/PingFang.ttc"]

        def _try_load(paths: List[str], size: int) -> Optional[ImageFont.FreeTypeFont]:
            for p in paths:
                try:
                    return ImageFont.truetype(p, size)
                except (OSError, IOError):
                    continue
            return None

        sizes_needed = {(p.font_size, p.bold) for p in self._paragraphs}

        for (size, bold) in sizes_needed:
            font = _try_load(bold_paths if bold else normal_paths, size)
            if font is None and bold:
                # Fallback: use normal font for bold
                font = _try_load(normal_paths, size)
            if font is None:
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()
            self._font_cache[(size, bold)] = font

    def _get_font(self, size: int, bold: bool) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self._font_cache:
            # Load on demand (shouldn't happen after _load_fonts, but safe)
            self._load_fonts()
        return self._font_cache.get(key, ImageFont.load_default())

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _measure_char_width(self, char: str, font: ImageFont.FreeTypeFont) -> float:
        """Measure a single character's width using getlength."""
        try:
            return font.getlength(char)
        except AttributeError:
            # Older Pillow fallback
            bbox = font.getbbox(char)
            return (bbox[2] - bbox[0]) if bbox else 6.0

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: float) -> List[str]:
        """Word/character-level greedy wrapping that handles CJK characters."""
        if not text:
            return [""]

        lines = []
        current_line = ""
        current_width = 0.0

        for char in text:
            char_width = self._measure_char_width(char, font)
            if current_width + char_width <= max_width:
                current_line += char
                current_width += char_width
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
                current_width = char_width

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def _paginate(self):
        """Split paragraphs into pages, recording line y-offsets."""
        usable_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        usable_height = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

        current_page = _PageRecord(para_start=0)
        current_y = 0.0

        for para_idx, para in enumerate(self._paragraphs):
            font = self._get_font(para.font_size, para.bold)
            line_height = para.font_size * LINE_HEIGHT_RATIO

            wrapped = self._wrap_text(para.text, font, usable_width)

            for line_text in wrapped:
                # Check if line fits on current page
                if current_y + line_height > usable_height and current_page.lines:
                    # Finish current page
                    current_page.para_end = para_idx
                    self._page_records.append(current_page)
                    current_page = _PageRecord(para_start=para_idx)
                    current_y = 0.0

                current_page.lines.append(_RenderedLine(
                    text=line_text,
                    y_offset=current_y,
                    font_size=para.font_size,
                    bold=para.bold,
                ))
                current_y += line_height

            # Add space after paragraph
            current_y += para.space_after

        # Finalize last page
        current_page.para_end = len(self._paragraphs)
        self._page_records.append(current_page)

        # Ensure at least one page
        if not self._page_records:
            self._page_records.append(_PageRecord(para_end=len(self._paragraphs)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_metadata(self) -> dict:
        """Get document metadata from core_properties."""
        title = ""
        author = ""
        try:
            props = self._doc.core_properties
            title = props.title or ""
            author = props.author or ""
        except Exception:
            pass

        return {
            "file_name": Path(self.file_path).name,
            "page_count": self.page_count,
            "title": title or Path(self.file_path).stem,
            "author": author,
            "subject": "Word Document",
        }

    def render_page(self, page_num: int, zoom: float = 1.0) -> str:
        """
        Render a page to a base64-encoded PNG image.

        Args:
            page_num: 1-based page number
            zoom: Zoom factor

        Returns:
            Base64-encoded PNG string (without data URI prefix)
        """
        cache_key = (page_num, round(zoom, 2))
        if cache_key in self._render_cache:
            return self._render_cache[cache_key]

        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        page = self._page_records[page_num - 1]
        img_width = int(PAGE_WIDTH * zoom)
        img_height = int(PAGE_HEIGHT * zoom)

        img = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(img)

        x_pos = int(MARGIN_LEFT * zoom)

        for rline in page.lines:
            y_pos = int((MARGIN_TOP + rline.y_offset) * zoom)
            scaled_size = max(1, int(rline.font_size * zoom))
            font = self._get_scaled_font(rline.font_size, rline.bold, scaled_size)
            draw.text((x_pos, y_pos), rline.text, fill="black", font=font)

        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        img_str = base64.b64encode(buffer.getvalue()).decode()

        self._render_cache[cache_key] = img_str
        return img_str

    def _get_scaled_font(self, base_size: int, bold: bool, scaled_size: int) -> ImageFont.FreeTypeFont:
        """Get a font at the given scaled size, reusing the same font file."""
        key = (scaled_size, bold)
        if key in self._font_cache:
            return self._font_cache[key]

        # Try to get the font path from existing cached font
        base_font = self._font_cache.get((base_size, bold))
        if base_font is not None:
            try:
                font_path = base_font.path
                new_font = ImageFont.truetype(font_path, scaled_size)
                self._font_cache[key] = new_font
                return new_font
            except (OSError, IOError, AttributeError):
                pass

        # Fallback: reload fonts at new size and cache
        old_paragraphs = self._paragraphs
        self._paragraphs = [_ParagraphInfo("", scaled_size, bold, 0)]
        self._load_fonts()
        self._paragraphs = old_paragraphs
        return self._font_cache.get(key, ImageFont.load_default())

    def extract_text(self, page_num: int, rect: Optional[dict] = None) -> str:
        """Extract text from a page."""
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")

        page = self._page_records[page_num - 1]
        paras = self._paragraphs[page.para_start:page.para_end]
        return "\n".join(p.text for p in paras)

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """Get page dimensions in points."""
        if page_num < 1 or page_num > self.page_count:
            raise ValueError(f"Invalid page number: {page_num}")
        return (PAGE_WIDTH, PAGE_HEIGHT)

    def search_text(self, query: str, page_num: Optional[int] = None) -> list:
        """
        Search for text in the document.

        Returns list of {page, rect: {x1, y1, x2, y2}} dicts.
        """
        results = []
        pages_to_search = [page_num] if page_num else range(1, self.page_count + 1)
        query_lower = query.lower()

        for pn in pages_to_search:
            page = self._page_records[pn - 1]
            for rline in page.lines:
                line_lower = rline.text.lower()
                start = 0
                while True:
                    pos = line_lower.find(query_lower, start)
                    if pos == -1:
                        break

                    font = self._get_font(rline.font_size, rline.bold)
                    try:
                        x1 = MARGIN_LEFT + font.getlength(rline.text[:pos])
                        x2 = x1 + font.getlength(query)
                    except AttributeError:
                        x1 = MARGIN_LEFT + pos * (rline.font_size * 0.6)
                        x2 = x1 + len(query) * (rline.font_size * 0.6)

                    y1 = MARGIN_TOP + rline.y_offset
                    y2 = y1 + rline.font_size * LINE_HEIGHT_RATIO

                    results.append({
                        "page": pn,
                        "rect": {
                            "x1": float(x1),
                            "y1": float(y1),
                            "x2": float(x2),
                            "y2": float(y2),
                        },
                    })
                    start = pos + 1

        return results

    def close(self):
        """Free resources."""
        self._render_cache.clear()
        self._font_cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
