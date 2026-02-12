"""
Note Editor Widget - Markdown note editing with PDF linking.

This widget provides:
- QTextEdit for markdown content editing
- Toolbar with formatting buttons
- Live preview mode
- PDF link support [[pdf:doc_id#page=N]]
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .preview_widget import MarkdownPreviewWidget


class NoteEditorWidget(QWidget):
    """
    Widget for editing markdown notes.

    Signals:
        noteContentChanged(str): Emitted when note content changes
        pdfLinkClicked(str): Emitted when a PDF link is clicked
    """

    noteContentChanged = Signal(str)
    pdfLinkClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_note_id: str | None = None
        self._is_editing = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title_bar = self._create_title_bar()
        layout.addWidget(self._title_bar)

        # Toolbar
        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)

        # Content area (editor + preview)
        self._content_stack = QStackedWidget(self)

        # Editor
        self._editor = QTextEdit(self)
        self._editor.setPlaceholderText("Start writing your notes here...\n\nUse [[pdf:doc_id#page=N]] to link to PDF pages.")
        self._editor.textChanged.connect(self._on_content_changed)
        self._content_stack.addWidget(self._editor)

        # Preview
        self._preview = MarkdownPreviewWidget(self)
        self._preview.pdfLinkClicked.connect(self.pdfLinkClicked)
        self._content_stack.addWidget(self._preview)

        layout.addWidget(self._content_stack)

        # Bottom toolbar
        self._bottom_bar = self._create_bottom_bar()
        layout.addWidget(self._bottom_bar)

    def _create_title_bar(self) -> QWidget:
        """Create the title bar with note title input."""
        bar = QWidget(self)
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        # Title label
        title_label = QLabel("Title:", bar)
        layout.addWidget(title_label)

        # Title input
        self._title_input = QLineEdit(bar)
        self._title_input.setPlaceholderText("Untitled Note")
        layout.addWidget(self._title_input)

        return bar

    def _create_toolbar(self) -> QToolBar:
        """Create the formatting toolbar."""
        toolbar = QToolBar(self)
        toolbar.setMovable(False)

        # Bold button
        bold_btn = QPushButton("B", toolbar)
        bold_btn.setToolTip("Bold (Ctrl+B)")
        bold_btn.setFixedSize(32, 28)
        bold_btn.setShortcut("Ctrl+B")
        bold_font = QFont(bold_btn.font())
        bold_font.setBold(True)
        bold_btn.setFont(bold_font)
        bold_btn.clicked.connect(self._insert_bold)
        toolbar.addWidget(bold_btn)

        # Italic button
        italic_btn = QPushButton("I", toolbar)
        italic_btn.setToolTip("Italic (Ctrl+I)")
        italic_btn.setFixedSize(32, 28)
        italic_btn.setShortcut("Ctrl+I")
        italic_font = QFont(italic_btn.font())
        italic_font.setItalic(True)
        italic_btn.setFont(italic_font)
        italic_btn.clicked.connect(self._insert_italic)
        toolbar.addWidget(italic_btn)

        # Heading buttons
        toolbar.addSeparator()

        h1_btn = QPushButton("H1", toolbar)
        h1_btn.setToolTip("Heading 1")
        h1_btn.setFixedSize(36, 28)
        h1_btn.clicked.connect(lambda: self._insert_heading(1))
        toolbar.addWidget(h1_btn)

        h2_btn = QPushButton("H2", toolbar)
        h2_btn.setToolTip("Heading 2")
        h2_btn.setFixedSize(36, 28)
        h2_btn.clicked.connect(lambda: self._insert_heading(2))
        toolbar.addWidget(h2_btn)

        h3_btn = QPushButton("H3", toolbar)
        h3_btn.setToolTip("Heading 3")
        h3_btn.setFixedSize(36, 28)
        h3_btn.clicked.connect(lambda: self._insert_heading(3))
        toolbar.addWidget(h3_btn)

        # List buttons
        toolbar.addSeparator()

        ul_btn = QPushButton("• List", toolbar)
        ul_btn.setToolTip("Bullet List")
        ul_btn.setFixedSize(50, 28)
        ul_btn.clicked.connect(self._insert_bullet_list)
        toolbar.addWidget(ul_btn)

        ol_btn = QPushButton("1. List", toolbar)
        ol_btn.setToolTip("Numbered List")
        ol_btn.setFixedSize(50, 28)
        ol_btn.clicked.connect(self._insert_numbered_list)
        toolbar.addWidget(ol_btn)

        # Link button
        toolbar.addSeparator()

        link_btn = QPushButton("🔗 Link", toolbar)
        link_btn.setToolTip("Insert PDF Link")
        link_btn.setFixedSize(60, 28)
        link_btn.clicked.connect(self._insert_pdf_link)
        toolbar.addWidget(link_btn)

        return toolbar

    def _create_bottom_bar(self) -> QWidget:
        """Create the bottom toolbar with mode switch and actions."""
        bar = QWidget(self)
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)

        # Mode toggle buttons
        self._edit_btn = QPushButton("Edit", bar)
        self._edit_btn.setCheckable(True)
        self._edit_btn.setChecked(True)
        self._edit_btn.clicked.connect(self._switch_to_edit)
        layout.addWidget(self._edit_btn)

        self._preview_btn = QPushButton("Preview", bar)
        self._preview_btn.setCheckable(True)
        self._preview_btn.setChecked(False)
        self._preview_btn.clicked.connect(self._switch_to_preview)
        layout.addWidget(self._preview_btn)

        layout.addStretch()

        # Export button
        export_btn = QPushButton("Export", bar)
        export_btn.setToolTip("Export note as Markdown")
        export_btn.clicked.connect(self._export_note)
        layout.addWidget(export_btn)

        return bar

    def _insert_bold(self) -> None:
        """Insert bold markdown syntax."""
        self._insert_wrapped_text("**", "**")

    def _insert_italic(self) -> None:
        """Insert italic markdown syntax."""
        self._insert_wrapped_text("*", "*")

    def _insert_heading(self, level: int) -> None:
        """Insert heading markdown syntax."""
        prefix = "#" * level + " "
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(prefix)
        self._editor.setFocus()

    def _insert_bullet_list(self) -> None:
        """Insert bullet list item."""
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText("- ")
        self._editor.setFocus()

    def _insert_numbered_list(self) -> None:
        """Insert numbered list item."""
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText("1. ")
        self._editor.setFocus()

    def _insert_pdf_link(self) -> None:
        """Insert PDF link syntax."""
        self._insert_wrapped_text("[[pdf:", "#page=1]]")

    def _insert_wrapped_text(self, before: str, after: str) -> None:
        """Insert text wrapped with before/after strings."""
        cursor = self._editor.textCursor()

        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(f"{before}{selected_text}{after}")
        else:
            cursor.insertText(f"{before}{after}")
            # Move cursor between the markers
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.MoveAnchor, len(after))

        self._editor.setFocus()

    def _switch_to_edit(self) -> None:
        """Switch to edit mode."""
        self._is_editing = True
        self._edit_btn.setChecked(True)
        self._preview_btn.setChecked(False)
        self._content_stack.setCurrentIndex(0)
        self._editor.setFocus()

    def _switch_to_preview(self) -> None:
        """Switch to preview mode."""
        self._is_editing = False
        self._edit_btn.setChecked(False)
        self._preview_btn.setChecked(True)
        self._preview.set_markdown(self._editor.toPlainText())
        self._content_stack.setCurrentIndex(1)

    def _on_content_changed(self) -> None:
        """Handle content changes in the editor."""
        content = self._editor.toPlainText()
        self.noteContentChanged.emit(content)

    def _export_note(self) -> None:
        """Export the note (placeholder for future implementation)."""
        # TODO: Implement export functionality
        pass

    def set_note(self, note_id: str | None, title: str, content: str) -> None:
        """
        Load a note into the editor.

        Args:
            note_id: The unique identifier for the note
            title: The note title
            content: The note content (markdown)
        """
        self._current_note_id = note_id
        self._title_input.setText(title)
        self._editor.setPlainText(content)

    def get_note_id(self) -> str | None:
        """Get the current note ID."""
        return self._current_note_id

    def get_title(self) -> str:
        """Get the current note title."""
        return self._title_input.text()

    def get_content(self) -> str:
        """Get the current note content."""
        return self._editor.toPlainText()

    def clear(self) -> None:
        """Clear the editor."""
        self._current_note_id = None
        self._title_input.clear()
        self._editor.clear()
