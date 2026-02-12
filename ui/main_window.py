"""
Main Window for DeepRead AI.

Layout:
- Horizontal splitter with PDF viewer (left, 60%) and note editor (right, 40%)
- Toolbar with open PDF, save note buttons
- Status bar showing current page and document info
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .ai_panel.chat_widget import AIChatWidget
from .ai_panel.context_menu import AIAction, AIContextMenu
from .components.toast import Toast
from .note_editor.editor_widget import NoteEditorWidget
from .pdf_viewer.viewer_widget import PDFViewerWidget
from .styles.theme import theme
from .styles.icons import Icons, get_icon_text


class MainWindow(QMainWindow):
    """
    Main application window for DeepRead AI.

    Signals:
        openPdfRequested(str): Emitted when user requests to open a PDF file
        saveNoteRequested(str, str, str): Emitted when user requests to save a note (note_id, title, content)
        pdfLinkClicked(str): Emitted when a PDF link is clicked in notes
        aiActionRequested(str, str): Emitted when an AI action is requested (action_type, selected_text)
        chatMessageSent(str): Emitted when user sends a message in chat (message)
    """

    openPdfRequested = Signal(str)
    saveNoteRequested = Signal(str, str, str)  # note_id, title, content
    pdfLinkClicked = Signal(str)
    aiActionRequested = Signal(str, str)  # action_type, selected_text
    chatMessageSent = Signal(str)  # message

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("DeepRead AI")
        self.setMinimumSize(800, 600)
        self.resize(1400, 900)

        # Apply theme stylesheet
        self.setStyleSheet(theme.get_stylesheet())

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_shortcuts()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Initialize the main UI layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create splitter for resizable panels
        self._splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)

        # PDF Viewer (left panel)
        self._pdf_viewer = PDFViewerWidget(self._splitter)
        self._pdf_viewer.pageChanged.connect(self._on_page_changed)
        self._pdf_viewer.textSelected.connect(self._on_text_selected)
        self._pdf_viewer.selectionCleared.connect(self._on_selection_cleared)

        # Right side container with stacked widgets (Note Editor / AI Chat)
        self._right_panel = QWidget(self._splitter)
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Note Editor
        self._note_editor = NoteEditorWidget(self._right_panel)
        self._note_editor.pdfLinkClicked.connect(self._on_pdf_link_clicked)

        # AI Chat Panel
        self._ai_chat = AIChatWidget(self._right_panel)
        self._ai_chat.messageSent.connect(self._on_chat_message_sent)
        self._ai_chat.quickActionTriggered.connect(self._on_quick_action_triggered)
        self._ai_chat.citationClicked.connect(self._on_citation_clicked)

        # Add both to right panel layout
        right_layout.addWidget(self._note_editor)
        right_layout.addWidget(self._ai_chat)

        # Show note editor by default, hide AI chat
        self._ai_chat.hide()
        self._right_panel_mode = "notes"  # "notes" or "ai"

        # Add widgets to splitter
        self._splitter.addWidget(self._pdf_viewer)
        self._splitter.addWidget(self._right_panel)

        # Set initial sizes (60% / 40%)
        self._splitter.setSizes([840, 560])

        # Set stretch factors to maintain proportions
        self._splitter.setStretchFactor(0, 6)
        self._splitter.setStretchFactor(1, 4)

        layout.addWidget(self._splitter)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open PDF...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_pdf)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_note_action = QAction("Save Note", self)
        save_note_action.setShortcut(QKeySequence.StandardKey.Save)
        save_note_action.triggered.connect(self._on_save_note)
        file_menu.addAction(save_note_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menu_bar.addMenu("View")

        self._maximize_pdf_action = QAction("Maximize PDF Viewer", self)
        self._maximize_pdf_action.setCheckable(True)
        self._maximize_pdf_action.triggered.connect(self._on_toggle_pdf_maximize)
        view_menu.addAction(self._maximize_pdf_action)

        self._maximize_note_action = QAction("Maximize Note Editor", self)
        self._maximize_note_action.setCheckable(True)
        self._maximize_note_action.triggered.connect(self._on_toggle_note_maximize)
        view_menu.addAction(self._maximize_note_action)

        view_menu.addSeparator()

        reset_layout_action = QAction("Reset Layout", self)
        reset_layout_action.triggered.connect(self._on_reset_layout)
        view_menu.addAction(reset_layout_action)

        view_menu.addSeparator()

        # Toggle AI Panel / Note Editor
        self._toggle_ai_panel_action = QAction("Show AI Panel", self)
        self._toggle_ai_panel_action.setCheckable(True)
        self._toggle_ai_panel_action.triggered.connect(self._on_toggle_ai_panel)
        view_menu.addAction(self._toggle_ai_panel_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")

        about_action = QAction("About DeepRead AI", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Set up the main toolbar."""
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open PDF button with icon
        open_btn = QPushButton(f" {Icons.OPEN} Open PDF", toolbar)
        open_btn.setToolTip("Open a PDF file (Ctrl+O)")
        open_btn.clicked.connect(self._on_open_pdf)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        # Save Note button with icon
        save_btn = QPushButton(f" {Icons.SAVE} Save Note", toolbar)
        save_btn.setToolTip("Save current note (Ctrl+S)")
        save_btn.clicked.connect(self._on_save_note)
        toolbar.addWidget(save_btn)

        toolbar.addSeparator()

        # AI Panel toggle button
        self._ai_toggle_btn = QPushButton(f" {Icons.SPARKLE} AI Panel", toolbar)
        self._ai_toggle_btn.setToolTip("Toggle AI Panel (Ctrl+Shift+A)")
        self._ai_toggle_btn.setCheckable(True)
        self._ai_toggle_btn.clicked.connect(self._on_ai_toggle_clicked)
        toolbar.addWidget(self._ai_toggle_btn)

        # Add a stretchable widget to push settings to the right
        spacer = QWidget(toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Settings button with icon
        settings_btn = QPushButton(f" {Icons.SETTINGS} Settings", toolbar)
        settings_btn.setToolTip("Application settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)

        # Page info label
        self._page_info_label = QLabel("No document open")
        self._status_bar.addWidget(self._page_info_label)

        self._status_bar.showMessage("Ready")

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # F11 for fullscreen toggle
        fullscreen_shortcut = QAction(self)
        fullscreen_shortcut.setShortcut("F11")
        fullscreen_shortcut.triggered.connect(self._toggle_fullscreen)
        self.addAction(fullscreen_shortcut)

    def _on_open_pdf(self) -> None:
        """Handle open PDF action."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            "",
            "PDF Files (*.pdf);;All Files (*.*)"
        )
        if file_path:
            self.openPdfRequested.emit(file_path)

    def _on_save_note(self) -> None:
        """Handle save note action."""
        note_id = self._note_editor.get_note_id()
        title = self._note_editor.get_title()
        content = self._note_editor.get_content()
        self.saveNoteRequested.emit(note_id or "", title, content)

    def _on_page_changed(self, page_num: int) -> None:
        """Handle page change from PDF viewer."""
        page_count = self._pdf_viewer.get_page_count()
        self._page_info_label.setText(f"Page {page_num} of {page_count}")

    def _on_pdf_link_clicked(self, pdf_ref: str) -> None:
        """Handle PDF link click from note editor."""
        self.pdfLinkClicked.emit(pdf_ref)

    def _on_toggle_pdf_maximize(self, checked: bool) -> None:
        """Toggle PDF viewer maximization."""
        if checked:
            self._splitter.setSizes([self.width(), 0])
            self._maximize_note_action.setChecked(False)
        else:
            self._on_reset_layout()

    def _on_toggle_note_maximize(self, checked: bool) -> None:
        """Toggle note editor maximization."""
        if checked:
            self._splitter.setSizes([0, self.width()])
            self._maximize_pdf_action.setChecked(False)
        else:
            self._on_reset_layout()

    def _on_reset_layout(self) -> None:
        """Reset the layout to default 60/40 split."""
        self._maximize_pdf_action.setChecked(False)
        self._maximize_note_action.setChecked(False)
        width = self._splitter.width()
        self._splitter.setSizes([int(width * 0.6), int(width * 0.4)])

    def _on_toggle_ai_panel(self, checked: bool) -> None:
        """Toggle between AI panel and note editor."""
        if checked:
            self._show_ai_panel()
        else:
            self._show_note_editor()

    def _on_ai_toggle_clicked(self) -> None:
        """Handle AI toggle button click."""
        self._on_toggle_ai_panel(self._ai_toggle_btn.isChecked())

    def _show_ai_panel(self) -> None:
        """Show the AI chat panel."""
        self._note_editor.hide()
        self._ai_chat.show()
        self._right_panel_mode = "ai"
        self._toggle_ai_panel_action.setChecked(True)
        self._toggle_ai_panel_action.setText("Show Notes")
        self._ai_toggle_btn.setChecked(True)
        self._ai_toggle_btn.setText(f" {Icons.NOTE} Notes")
        self.show_status_message("AI Panel active")

    def _show_note_editor(self) -> None:
        """Show the note editor."""
        self._ai_chat.hide()
        self._note_editor.show()
        self._right_panel_mode = "notes"
        self._toggle_ai_panel_action.setChecked(False)
        self._toggle_ai_panel_action.setText("Show AI Panel")
        self._ai_toggle_btn.setChecked(False)
        self._ai_toggle_btn.setText(f" {Icons.SPARKLE} AI Panel")
        self.show_status_message("Notes active")

    def _setup_connections(self) -> None:
        """Set up signal connections for AI integration."""
        # AI Context Menu will be created on demand
        self._ai_context_menu: Optional[AIContextMenu] = None

    def _on_text_selected(self, text: str, rect: object, page_num: int) -> None:
        """Handle text selection from PDF viewer."""
        # Create context menu if needed
        if self._ai_context_menu is None:
            self._ai_context_menu = AIContextMenu(self)
            self._ai_context_menu.actionTriggered.connect(self._on_ai_action_triggered)
            self._ai_context_menu.dismissed.connect(self._on_context_menu_dismissed)

        # Show context menu near selection
        self._ai_context_menu.show_at_selection(text, rect, self)

    def _on_selection_cleared(self) -> None:
        """Handle selection cleared from PDF viewer."""
        if self._ai_context_menu is not None:
            self._ai_context_menu.hide_menu()

    def _on_ai_action_triggered(self, action: AIAction, text: str) -> None:
        """Handle AI action from context menu."""
        # Switch to AI panel
        self._show_ai_panel()

        # Emit the action
        self.aiActionRequested.emit(action.value, text)

        # Show feedback
        action_names = {
            AIAction.EXPLAIN: "Explaining",
            AIAction.TRANSLATE: "Translating",
            AIAction.SUMMARIZE: "Summarizing",
            AIAction.DEFINE: "Defining",
            AIAction.ASK_AI: "Asking AI about",
        }
        Toast.show_info(f"{action_names.get(action, 'Processing')} selected text...")

    def _on_context_menu_dismissed(self) -> None:
        """Handle context menu dismissed."""
        # Clear selection when menu is dismissed (but don't recurse)
        if self._pdf_viewer.get_selection_layer().has_selection():
            self._pdf_viewer.clear_selection()

    def _on_chat_message_sent(self, message: str) -> None:
        """Handle chat message sent."""
        self.chatMessageSent.emit(message)

    def _on_quick_action_triggered(self, action: str) -> None:
        """Handle quick action triggered."""
        # Add user message showing the action
        self._ai_chat.add_user_message(f"[{action}]")
        self.aiActionRequested.emit(action.lower().replace(" ", "_"), "")

    def _on_citation_clicked(self, page_num: int) -> None:
        """Handle citation clicked in chat."""
        self._pdf_viewer.go_to_page(page_num)
        Toast.show_info(f"Jumped to page {page_num}")

    def get_ai_chat(self) -> AIChatWidget:
        """Get the AI chat widget."""
        return self._ai_chat

    def add_ai_message(self, text: str, citations: Optional[list] = None) -> None:
        """Add an AI message to the chat."""
        self._ai_chat.add_ai_message(text, citations)

    def show_toast(self, message: str, severity: str = "info") -> None:
        """Show a toast notification."""
        from .components.toast import ToastSeverity

        severity_map = {
            "info": ToastSeverity.INFO,
            "success": ToastSeverity.SUCCESS,
            "warning": ToastSeverity.WARNING,
            "error": ToastSeverity.ERROR,
        }

        severity_enum = severity_map.get(severity, ToastSeverity.INFO)

        if severity == "success":
            Toast.show_success(message)
        elif severity == "warning":
            Toast.show_warning(message)
        elif severity == "error":
            Toast.show_error(message)
        else:
            Toast.show_info(message)

    def _on_settings(self) -> None:
        """Handle settings action (placeholder)."""
        # TODO: Implement settings dialog
        pass

    def _on_about(self) -> None:
        """Handle about action."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About DeepRead AI",
            "<h2>DeepRead AI</h2>"
            "<p>Version 0.1.0</p>"
            "<p>An AI-powered PDF reader with integrated note-taking.</p>"
            "<p>Built with PySide6.</p>"
        )

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def get_pdf_viewer(self) -> PDFViewerWidget:
        """Get the PDF viewer widget."""
        return self._pdf_viewer

    def get_note_editor(self) -> NoteEditorWidget:
        """Get the note editor widget."""
        return self._note_editor

    def show_status_message(self, message: str, timeout: int = 3000) -> None:
        """Show a temporary status message."""
        self._status_bar.showMessage(message, timeout)


# Need to import QLabel here for status bar
from PySide6.QtWidgets import QLabel
