"""
PDF Viewer Widget - Displays PDF pages using QPixmap.

This widget provides:
- QLabel-based display for QPixmap
- Scroll area for large pages
- Zoom in/out functionality
- Basic navigation controls
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .selection_layer import HighlightColor, SelectionLayer


class PDFViewerWidget(QWidget):
    """
    Widget for displaying PDF pages.

    Signals:
        pageChanged(int): Emitted when the current page changes
        zoomChanged(float): Emitted when the zoom level changes
        textSelected(str, QRect, int): Emitted when text is selected in the PDF
        selectionCleared(): Emitted when text selection is cleared
    """

    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    textSelected = Signal(str, object, int)  # text, QRect, page_num
    selectionCleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_page = 0
        self._page_count = 0
        self._zoom = 1.0
        self._min_zoom = 0.25
        self._max_zoom = 4.0
        self._zoom_step = 1.25

        # Renderer will be set by user
        self._renderer = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for the PDF display
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Container widget for page and selection overlay
        self._page_container = QWidget(self._scroll_area)
        self._page_container.setStyleSheet("background-color: transparent;")
        # No layout - we'll position widgets manually for proper overlay

        # Label to display the PDF page
        self._page_label = QLabel(self._page_container)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setText("No PDF loaded")
        self._page_label.setStyleSheet("color: #757575; font-size: 16px;")

        # Selection layer overlay - positioned on top of page label
        self._selection_layer = SelectionLayer(self._page_container)
        self._selection_layer.textSelected.connect(self._on_text_selected)
        self._selection_layer.selectionCleared.connect(self.selectionCleared.emit)
        self._selection_layer.hide()  # Hidden until PDF is loaded

        self._scroll_area.setWidget(self._page_container)
        layout.addWidget(self._scroll_area)

        # Navigation bar at the bottom
        self._nav_bar = self._create_nav_bar()
        layout.addWidget(self._nav_bar)

    def _create_nav_bar(self) -> QWidget:
        """Create the navigation bar with page controls."""
        nav_bar = QWidget(self)
        nav_bar.setFixedHeight(48)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(12, 6, 12, 6)
        nav_layout.setSpacing(8)

        # Previous page button - using Unicode arrows that render well on Linux
        self._prev_btn = QToolButton(nav_bar)
        self._prev_btn.setText("←")
        self._prev_btn.setToolTip("Previous Page (←)")
        self._prev_btn.setEnabled(False)
        self._prev_btn.setFont(QFont("DejaVu Sans", 14))
        self._prev_btn.clicked.connect(self._on_prev_page)
        nav_layout.addWidget(self._prev_btn)

        # Page number input
        self._page_input = QSpinBox(nav_bar)
        self._page_input.setMinimum(1)
        self._page_input.setMaximum(1)
        self._page_input.setValue(1)
        self._page_input.setFixedWidth(60)
        self._page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_input.valueChanged.connect(self._on_page_input_changed)
        nav_layout.addWidget(self._page_input)

        # Page count label
        self._page_count_label = QLabel("/ 1", nav_bar)
        self._page_count_label.setStyleSheet("color: #757575;")
        nav_layout.addWidget(self._page_count_label)

        # Next page button
        self._next_btn = QToolButton(nav_bar)
        self._next_btn.setText("→")
        self._next_btn.setToolTip("Next Page (→)")
        self._next_btn.setEnabled(False)
        self._next_btn.setFont(QFont("DejaVu Sans", 14))
        self._next_btn.clicked.connect(self._on_next_page)
        nav_layout.addWidget(self._next_btn)

        nav_layout.addStretch()

        # Zoom out button
        self._zoom_out_btn = QToolButton(nav_bar)
        self._zoom_out_btn.setText("−")
        self._zoom_out_btn.setToolTip("Zoom Out (Ctrl+-)")
        self._zoom_out_btn.setEnabled(False)
        self._zoom_out_btn.setFont(QFont("DejaVu Sans", 12))
        self._zoom_out_btn.clicked.connect(self._on_zoom_out)
        nav_layout.addWidget(self._zoom_out_btn)

        # Zoom level display
        self._zoom_label = QLabel("100%", nav_bar)
        self._zoom_label.setFixedWidth(50)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self._zoom_label)

        # Zoom in button
        self._zoom_in_btn = QToolButton(nav_bar)
        self._zoom_in_btn.setText("+")
        self._zoom_in_btn.setToolTip("Zoom In (Ctrl++)")
        self._zoom_in_btn.setEnabled(False)
        self._zoom_in_btn.setFont(QFont("DejaVu Sans", 12))
        self._zoom_in_btn.clicked.connect(self._on_zoom_in)
        nav_layout.addWidget(self._zoom_in_btn)

        # Fit to width button
        self._fit_btn = QToolButton(nav_bar)
        self._fit_btn.setText("⤢")
        self._fit_btn.setToolTip("Fit to Width (Ctrl+0)")
        self._fit_btn.setEnabled(False)
        self._fit_btn.setFont(QFont("DejaVu Sans", 12))
        self._fit_btn.clicked.connect(self._on_fit_to_width)
        nav_layout.addWidget(self._fit_btn)

        # Highlight color selector
        nav_layout.addSpacing(20)

        self._highlight_btn_yellow = QToolButton(nav_bar)
        self._highlight_btn_yellow.setToolTip("Yellow highlight")
        self._highlight_btn_yellow.setCheckable(True)
        self._highlight_btn_yellow.setChecked(True)
        self._highlight_btn_yellow.setFixedSize(28, 28)
        self._highlight_btn_yellow.setStyleSheet(
            "QToolButton { background-color: #fbbf24; border-radius: 4px; border: 2px solid transparent; }"
            "QToolButton:hover { border-color: #9ca3af; }"
            "QToolButton:checked { border: 2px solid #1a73e8; }"
        )
        self._highlight_btn_yellow.clicked.connect(
            lambda: self._on_highlight_color_changed(HighlightColor.YELLOW)
        )
        nav_layout.addWidget(self._highlight_btn_yellow)

        self._highlight_btn_green = QToolButton(nav_bar)
        self._highlight_btn_green.setToolTip("Green highlight")
        self._highlight_btn_green.setCheckable(True)
        self._highlight_btn_green.setFixedSize(28, 28)
        self._highlight_btn_green.setStyleSheet(
            "QToolButton { background-color: #4ade80; border-radius: 4px; border: 2px solid transparent; }"
            "QToolButton:hover { border-color: #9ca3af; }"
            "QToolButton:checked { border: 2px solid #1a73e8; }"
        )
        self._highlight_btn_green.clicked.connect(
            lambda: self._on_highlight_color_changed(HighlightColor.GREEN)
        )
        nav_layout.addWidget(self._highlight_btn_green)

        self._highlight_btn_blue = QToolButton(nav_bar)
        self._highlight_btn_blue.setToolTip("Blue highlight")
        self._highlight_btn_blue.setCheckable(True)
        self._highlight_btn_blue.setFixedSize(28, 28)
        self._highlight_btn_blue.setStyleSheet(
            "QToolButton { background-color: #60a5fa; border-radius: 4px; border: 2px solid transparent; }"
            "QToolButton:hover { border-color: #9ca3af; }"
            "QToolButton:checked { border: 2px solid #1a73e8; }"
        )
        self._highlight_btn_blue.clicked.connect(
            lambda: self._on_highlight_color_changed(HighlightColor.BLUE)
        )
        nav_layout.addWidget(self._highlight_btn_blue)

        self._highlight_btn_pink = QToolButton(nav_bar)
        self._highlight_btn_pink.setToolTip("Pink highlight")
        self._highlight_btn_pink.setCheckable(True)
        self._highlight_btn_pink.setFixedSize(28, 28)
        self._highlight_btn_pink.setStyleSheet(
            "QToolButton { background-color: #f472b6; border-radius: 4px; border: 2px solid transparent; }"
            "QToolButton:hover { border-color: #9ca3af; }"
            "QToolButton:checked { border: 2px solid #1a73e8; }"
        )
        self._highlight_btn_pink.clicked.connect(
            lambda: self._on_highlight_color_changed(HighlightColor.PINK)
        )
        nav_layout.addWidget(self._highlight_btn_pink)

        return nav_bar

    def set_renderer(self, renderer) -> None:
        """
        Set the PDF renderer.

        The renderer must implement:
            - render_page(page_num: int, zoom: float) -> QPixmap
            - get_page_count() -> int
        """
        self._renderer = renderer
        if renderer is not None:
            self._page_count = renderer.get_page_count()
            self._update_page_count()
            self._enable_controls(True)
            if self._page_count > 0:
                self.go_to_page(1)
            # Set up text extraction for selection layer
            self._selection_layer.set_text_extractor(self._extract_text_from_rect)
        else:
            self._page_count = 0
            self._current_page = 0
            self._page_label.setText("No PDF loaded")
            self._page_label.setPixmap(QPixmap())
            self._update_page_count()
            self._enable_controls(False)
            self._selection_layer.set_text_extractor(None)

    def _enable_controls(self, enabled: bool) -> None:
        """Enable or disable navigation controls."""
        self._prev_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)
        self._zoom_in_btn.setEnabled(enabled)
        self._zoom_out_btn.setEnabled(enabled)
        self._fit_btn.setEnabled(enabled)
        self._page_input.setEnabled(enabled)

    def _update_page_count(self) -> None:
        """Update the page count display."""
        self._page_count_label.setText(f"/ {self._page_count}")
        self._page_input.setMaximum(max(1, self._page_count))

    def _update_page_display(self) -> None:
        """Update the page display with the current page."""
        if self._renderer is None or self._current_page < 1:
            return

        pixmap = self._renderer.render_page(self._current_page, self._zoom)
        if pixmap and not pixmap.isNull():
            self._page_label.setPixmap(pixmap)
            self._page_label.setText("")
            self._page_label.resize(pixmap.size())
            self._page_container.setMinimumSize(pixmap.size())
            # Update selection layer geometry to match page
            self._update_selection_layer_geometry()
            # Update selection layer page and zoom
            self._selection_layer.set_current_page(self._current_page)
            self._selection_layer.set_zoom(self._zoom)
        else:
            self._page_label.setText(f"Failed to render page {self._current_page}")
            self._page_label.setPixmap(QPixmap())

    def _update_nav_buttons(self) -> None:
        """Update navigation button states."""
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._page_count)
        self._page_input.setValue(self._current_page)

    def _update_zoom_display(self) -> None:
        """Update the zoom level display."""
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")

    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        if self._current_page > 1:
            self.go_to_page(self._current_page - 1)

    def _on_next_page(self) -> None:
        """Handle next page button click."""
        if self._current_page < self._page_count:
            self.go_to_page(self._current_page + 1)

    def _on_page_input_changed(self, value: int) -> None:
        """Handle page number input change."""
        if value != self._current_page:
            self.go_to_page(value)

    def _on_zoom_in(self) -> None:
        """Handle zoom in button click."""
        new_zoom = min(self._zoom * self._zoom_step, self._max_zoom)
        self.set_zoom(new_zoom)

    def _on_zoom_out(self) -> None:
        """Handle zoom out button click."""
        new_zoom = max(self._zoom / self._zoom_step, self._min_zoom)
        self.set_zoom(new_zoom)

    def _on_fit_to_width(self) -> None:
        """Handle fit to width button click."""
        # Calculate zoom to fit page width to scroll area
        if self._renderer is None:
            return

        # Get the current page at 100% zoom to determine size
        pixmap = self._renderer.render_page(self._current_page, 1.0)
        if pixmap and not pixmap.isNull():
            available_width = self._scroll_area.viewport().width() - 40
            new_zoom = available_width / pixmap.width()
            new_zoom = max(self._min_zoom, min(new_zoom, self._max_zoom))
            self.set_zoom(new_zoom)

    def go_to_page(self, page_num: int) -> None:
        """
        Navigate to a specific page.

        Args:
            page_num: The 1-based page number to navigate to
        """
        if page_num < 1 or page_num > self._page_count:
            return

        self._current_page = page_num
        self._update_page_display()
        self._update_nav_buttons()
        self.pageChanged.emit(self._current_page)

    def set_zoom(self, zoom: float) -> None:
        """
        Set the zoom level.

        Args:
            zoom: The zoom factor (1.0 = 100%)
        """
        zoom = max(self._min_zoom, min(zoom, self._max_zoom))
        if zoom != self._zoom:
            self._zoom = zoom
            self._update_zoom_display()
            self._update_page_display()
            self.zoomChanged.emit(self._zoom)

    def get_current_page(self) -> int:
        """Get the current page number (1-based)."""
        return self._current_page

    def get_zoom(self) -> float:
        """Get the current zoom level."""
        return self._zoom

    def get_page_count(self) -> int:
        """Get the total number of pages."""
        return self._page_count

    def _update_selection_layer_geometry(self) -> None:
        """Update the selection layer geometry to match the page label."""
        if self._page_label.pixmap() and not self._page_label.pixmap().isNull():
            # Position selection layer over the page label at (0,0) of container
            pixmap_size = self._page_label.pixmap().size()
            self._selection_layer.setGeometry(0, 0, pixmap_size.width(), pixmap_size.height())
            self._selection_layer.show()
        else:
            self._selection_layer.hide()

    def _extract_text_from_rect(self, rect: object, page_num: int) -> str:
        """
        Extract text from a rectangular region on a page.

        This is a placeholder that should be overridden by the actual PDF renderer.
        Returns a mock text for demonstration.
        """
        # TODO: Implement actual text extraction using PyMuPDF
        # For now, return placeholder text
        return f"Selected text from page {page_num}"

    def _on_text_selected(self, text: str, rect: object, page_num: int) -> None:
        """Handle text selection from the selection layer."""
        self.textSelected.emit(text, rect, page_num)

    def _on_highlight_color_changed(self, color: HighlightColor) -> None:
        """Handle highlight color change."""
        # Uncheck all buttons
        self._highlight_btn_yellow.setChecked(False)
        self._highlight_btn_green.setChecked(False)
        self._highlight_btn_blue.setChecked(False)
        self._highlight_btn_pink.setChecked(False)

        # Check the selected button
        if color == HighlightColor.YELLOW:
            self._highlight_btn_yellow.setChecked(True)
        elif color == HighlightColor.GREEN:
            self._highlight_btn_green.setChecked(True)
        elif color == HighlightColor.BLUE:
            self._highlight_btn_blue.setChecked(True)
        elif color == HighlightColor.PINK:
            self._highlight_btn_pink.setChecked(True)

        self._selection_layer.set_highlight_color(color)

    def get_selection_layer(self) -> SelectionLayer:
        """Get the selection layer widget."""
        return self._selection_layer

    def clear_selection(self) -> None:
        """Clear the current text selection."""
        self._selection_layer.clear_selection()

    def keyPressEvent(self, event) -> None:
        """Handle keyboard navigation."""
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_PageUp:
            self._on_prev_page()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_PageDown:
            self._on_next_page()
        elif event.key() == Qt.Key.Key_Home:
            self.go_to_page(1)
        elif event.key() == Qt.Key.Key_End:
            self.go_to_page(self._page_count)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel for zoom with Ctrl modifier."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._on_zoom_in()
            elif delta < 0:
                self._on_zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
