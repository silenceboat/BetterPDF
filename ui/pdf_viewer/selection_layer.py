"""
Text Selection Overlay for PDF Viewer.

An invisible overlay that handles mouse text selection with visual feedback,
coordinate mapping from screen to PDF coordinates, and emits selected text
with position information.
"""

from enum import Enum
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from ..styles.theme import theme


class HighlightColor(Enum):
    """Available highlight colors for text selection."""
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PINK = "pink"


class SelectionLayer(QWidget):
    """
    Overlay widget for handling text selection on PDF pages.

    This widget sits on top of the PDF display and handles:
    - Mouse events for text selection
    - Drawing selection rectangles with highlight colors
    - Coordinate mapping between screen and PDF coordinates
    - Emitting selected text with position information

    Signals:
        textSelected(str, QRect, int): Emitted when text selection is complete
            - str: The selected text
            - QRect: The selection rectangle in screen coordinates
            - int: The current page number
        selectionCleared(): Emitted when selection is cleared
    """

    textSelected = Signal(str, QRect, int)
    selectionCleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Make transparent to mouse events when not selecting
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # Selection state
        self._is_selecting = False
        self._selection_start: Optional[QPoint] = None
        self._selection_end: Optional[QPoint] = None
        self._selection_rect = QRect()
        self._current_highlight_color = HighlightColor.YELLOW

        # Page tracking
        self._current_page = 1
        self._zoom = 1.0

        # Text extraction callback (set by parent)
        self._text_extractor: Optional[callable] = None

        # Enable mouse tracking
        self.setMouseTracking(True)

        # Set cursor to I-beam for text areas
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def set_text_extractor(self, extractor: callable) -> None:
        """
        Set the text extraction callback.

        The extractor should accept (rect: QRect, page_num: int) and return str.
        """
        self._text_extractor = extractor

    def set_current_page(self, page_num: int) -> None:
        """Set the current page number for selection tracking."""
        self._current_page = page_num
        self.clear_selection()

    def set_zoom(self, zoom: float) -> None:
        """Set the current zoom level for coordinate mapping."""
        self._zoom = zoom
        self.clear_selection()

    def set_highlight_color(self, color: HighlightColor) -> None:
        """Set the highlight color for new selections."""
        self._current_highlight_color = color

    def get_highlight_color(self) -> HighlightColor:
        """Get the current highlight color."""
        return self._current_highlight_color

    def clear_selection(self) -> None:
        """Clear the current selection."""
        had_selection = self.has_selection()
        self._is_selecting = False
        self._selection_start = None
        self._selection_end = None
        self._selection_rect = QRect()
        self.update()
        if had_selection:
            self.selectionCleared.emit()

    def get_selection_rect(self) -> QRect:
        """Get the current selection rectangle in screen coordinates."""
        return QRect(self._selection_rect)

    def has_selection(self) -> bool:
        """Check if there is an active selection."""
        return self._selection_rect.isValid() and not self._selection_rect.isEmpty()

    def _get_highlight_color_rgba(self) -> QColor:
        """Get the current highlight color as QColor."""
        colors = {
            HighlightColor.YELLOW: QColor(253, 224, 71, 102),  # 0.4 * 255
            HighlightColor.GREEN: QColor(134, 239, 172, 102),
            HighlightColor.BLUE: QColor(147, 197, 253, 102),
            HighlightColor.PINK: QColor(249, 168, 212, 102),
        }
        return colors.get(self._current_highlight_color, colors[HighlightColor.YELLOW])

    def _get_highlight_border_color(self) -> QColor:
        """Get a slightly darker border color for the highlight."""
        colors = {
            HighlightColor.YELLOW: QColor(234, 179, 8, 180),
            HighlightColor.GREEN: QColor(34, 197, 94, 180),
            HighlightColor.BLUE: QColor(59, 130, 246, 180),
            HighlightColor.PINK: QColor(236, 72, 153, 180),
        }
        return colors.get(self._current_highlight_color, colors[HighlightColor.YELLOW])

    def _normalize_selection_rect(self) -> QRect:
        """Normalize the selection rectangle (ensure positive width/height)."""
        if self._selection_start is None or self._selection_end is None:
            return QRect()

        x1 = min(self._selection_start.x(), self._selection_end.x())
        y1 = min(self._selection_start.y(), self._selection_end.y())
        x2 = max(self._selection_start.x(), self._selection_end.x())
        y2 = max(self._selection_start.y(), self._selection_end.y())

        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _extract_text_from_selection(self) -> str:
        """Extract text from the current selection using the text extractor."""
        if self._text_extractor is None or not self.has_selection():
            return ""

        try:
            return self._text_extractor(self._selection_rect, self._current_page)
        except Exception:
            return ""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to start selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = True
            self._selection_start = event.pos()
            self._selection_end = event.pos()
            self._selection_rect = QRect(self._selection_start, self._selection_end)
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move to update selection."""
        if self._is_selecting and self._selection_start is not None:
            self._selection_end = event.pos()
            self._selection_rect = self._normalize_selection_rect()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to complete selection."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._selection_end = event.pos()
            self._selection_rect = self._normalize_selection_rect()

            # Only emit if selection is meaningful (not just a click)
            if self._selection_rect.width() > 5 or self._selection_rect.height() > 5:
                selected_text = self._extract_text_from_selection()
                self.textSelected.emit(
                    selected_text,
                    QRect(self._selection_rect),
                    self._current_page
                )

            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the selection highlight."""
        if not self.has_selection():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill the selection area
        fill_color = self._get_highlight_color_rgba()
        painter.fillRect(self._selection_rect, fill_color)

        # Draw border
        border_color = self._get_highlight_border_color()
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(self._selection_rect.adjusted(0, 0, -1, -1))

    def screen_to_pdf_coords(self, screen_pos: QPoint) -> tuple[float, float]:
        """
        Convert screen coordinates to PDF coordinates.

        Returns:
            Tuple of (x, y) in PDF coordinates (0-1 normalized)
        """
        # Get the geometry relative to parent
        rect = self.geometry()
        rel_x = screen_pos.x() - rect.x()
        rel_y = screen_pos.y() - rect.y()

        # Convert to PDF coordinates (normalized 0-1)
        pdf_x = rel_x / (rect.width() * self._zoom) if rect.width() > 0 else 0
        pdf_y = rel_y / (rect.height() * self._zoom) if rect.height() > 0 else 0

        return (pdf_x, pdf_y)

    def pdf_to_screen_coords(self, pdf_x: float, pdf_y: float) -> QPoint:
        """
        Convert PDF coordinates to screen coordinates.

        Args:
            pdf_x: X coordinate in PDF (0-1 normalized)
            pdf_y: Y coordinate in PDF (0-1 normalized)

        Returns:
            QPoint in screen coordinates
        """
        rect = self.geometry()
        screen_x = rect.x() + int(pdf_x * rect.width() * self._zoom)
        screen_y = rect.y() + int(pdf_y * rect.height() * self._zoom)
        return QPoint(screen_x, screen_y)
