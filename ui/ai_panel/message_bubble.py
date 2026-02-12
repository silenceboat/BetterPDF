"""
Message Bubble Component for DeepRead AI Chat Interface.

Reusable message bubble widget for displaying chat messages with support for:
- User and AI message types
- Markdown rendering for AI responses
- Citation pills that link to PDF locations
- Copy button on hover for AI messages
"""

import re
from enum import Enum
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QClipboard, QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..styles.theme import theme, Typography


class MessageType(Enum):
    """Type of message bubble."""
    USER = "user"
    AI = "ai"


class CitationPill(QWidget):
    """
    A clickable citation pill showing a page reference.

    Signals:
        clicked(int): Emitted when the pill is clicked with the page number
    """

    clicked = Signal(int)

    def __init__(self, page_num: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._page_num = page_num

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(22)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._label = QLabel(f"p.{page_num}", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Medium)
        self._label.setFont(font)
        layout.addWidget(self._label)

        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply theme styles."""
        c = theme.colors

        self.setStyleSheet(f"""
            CitationPill {{
                background-color: rgba(37, 99, 235, 0.15);
                border-radius: 11px;
                color: {c.accent_primary};
            }}
            CitationPill:hover {{
                background-color: rgba(37, 99, 235, 0.25);
            }}
            QLabel {{
                color: {c.accent_primary};
                background: transparent;
                border: none;
            }}
        """)

    def mousePressEvent(self, event) -> None:
        """Handle click."""
        self.clicked.emit(self._page_num)

    def get_page_num(self) -> int:
        """Get the page number."""
        return self._page_num


class MessageBubble(QWidget):
    """
    Message bubble widget for chat interface.

    Supports both user and AI message types with appropriate styling.
    AI messages support markdown rendering and citation pills.

    Signals:
        citationClicked(int): Emitted when a citation pill is clicked
        copyClicked(str): Emitted when copy button is clicked
    """

    citationClicked = Signal(int)
    copyClicked = Signal(str)

    def __init__(
        self,
        message_type: MessageType,
        text: str,
        citations: Optional[List[int]] = None,
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self._message_type = message_type
        self._text = text
        self._citations = citations or []
        self._show_copy_button = False

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        if self._message_type == MessageType.USER:
            self._setup_user_message(layout)
        else:
            self._setup_ai_message(layout)

    def _setup_user_message(self, layout: QVBoxLayout) -> None:
        """Set up user message layout."""
        # User messages are right-aligned with card background
        self.setObjectName("userBubble")

        # Container for right alignment
        container = QWidget(self)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addStretch()

        # Message text
        self._text_label = QLabel(self._text, container)
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._text_label.setObjectName("messageText")
        container_layout.addWidget(self._text_label)

        layout.addWidget(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight)

    def _setup_ai_message(self, layout: QVBoxLayout) -> None:
        """Set up AI message layout."""
        self.setObjectName("aiBubble")

        # Header with AI indicator
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        ai_label = QLabel("AI", header)
        ai_label.setObjectName("aiLabel")
        font = QFont()
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Bold)
        ai_label.setFont(font)
        header_layout.addWidget(ai_label)

        header_layout.addStretch()

        # Copy button (hidden by default, shown on hover)
        self._copy_btn = QPushButton("Copy", header)
        self._copy_btn.setObjectName("copyBtn")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setFixedSize(50, 24)
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        self._copy_btn.hide()
        header_layout.addWidget(self._copy_btn)

        layout.addWidget(header)

        # Message content with markdown support
        self._text_edit = QTextEdit(self)
        self._text_edit.setObjectName("messageText")
        self._text_edit.setReadOnly(True)
        self._text_edit.setFrameStyle(0)
        self._text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._text_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Render markdown
        html_content = self._markdown_to_html(self._text)
        self._text_edit.setHtml(html_content)

        # Auto-adjust height
        doc_height = self._text_edit.document().size().height()
        self._text_edit.setFixedHeight(int(doc_height) + 10)

        layout.addWidget(self._text_edit)

        # Citations row
        if self._citations:
            citations_widget = QWidget(self)
            citations_layout = QHBoxLayout(citations_widget)
            citations_layout.setContentsMargins(0, 4, 0, 0)
            citations_layout.setSpacing(6)

            for page_num in self._citations:
                pill = CitationPill(page_num, citations_widget)
                pill.clicked.connect(self.citationClicked.emit)
                citations_layout.addWidget(pill)

            citations_layout.addStretch()
            layout.addWidget(citations_widget)

    def _markdown_to_html(self, text: str) -> str:
        """
        Convert markdown text to HTML for display.

        Basic markdown support:
        - Headers (# ## ###)
        - Bold (**text**)
        - Italic (*text*)
        - Code (`code` and ```code blocks```)
        - Lists (- and 1.)
        """
        c = theme.colors

        # Escape HTML
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        # Code blocks (```...```)
        def code_block_replacer(match):
            code = match.group(1)
            return f'<pre style="background-color: {c.background_canvas}; padding: 8px; border-radius: 4px; font-family: {Typography.CODE}; font-size: 12px; overflow-x: auto;"><code>{code}</code></pre>'

        text = re.sub(r'```(?:\w+)?\n(.*?)```', code_block_replacer, text, flags=re.DOTALL)

        # Inline code (`...`)
        text = re.sub(
            r'`([^`]+)`',
            rf'<code style="background-color: {c.background_canvas}; padding: 2px 4px; border-radius: 3px; font-family: {Typography.CODE}; font-size: 12px;">\1</code>',
            text
        )

        # Headers
        text = re.sub(
            r'^### (.+)$',
            rf'<h3 style="color: {c.text_primary}; font-family: {Typography.HEADING}; margin: 8px 0;">\1</h3>',
            text,
            flags=re.MULTILINE
        )
        text = re.sub(
            r'^## (.+)$',
            rf'<h2 style="color: {c.text_primary}; font-family: {Typography.HEADING}; margin: 12px 0 8px 0;">\1</h2>',
            text,
            flags=re.MULTILINE
        )
        text = re.sub(
            r'^# (.+)$',
            rf'<h1 style="color: {c.text_primary}; font-family: {Typography.HEADING}; margin: 16px 0 8px 0; font-size: 18px;">\1</h1>',
            text,
            flags=re.MULTILINE
        )

        # Bold
        text = re.sub(
            r'\*\*(.+?)\*\*',
            r'<strong>\1</strong>',
            text
        )

        # Italic
        text = re.sub(
            r'\*(.+?)\*',
            r'<em>\1</em>',
            text
        )

        # Unordered lists
        def ul_replacer(match):
            items = match.group(0).strip().split('\n')
            html_items = ''.join(
                f'<li style="margin: 4px 0;">{item[2:]}</li>'
                for item in items
            )
            return f'<ul style="margin: 8px 0; padding-left: 20px;">{html_items}</ul>'

        text = re.sub(r'(^- .+\n?)+', ul_replacer, text, flags=re.MULTILINE)

        # Ordered lists
        def ol_replacer(match):
            items = match.group(0).strip().split('\n')
            html_items = ''.join(
                f'<li style="margin: 4px 0;">{item[item.find(" ")+1:]}</li>'
                for item in items
            )
            return f'<ol style="margin: 8px 0; padding-left: 20px;">{html_items}</ol>'

        text = re.sub(r'(^\d+\. .+\n?)+', ol_replacer, text, flags=re.MULTILINE)

        # Paragraphs (double newline)
        paragraphs = text.split('\n\n')
        html_paragraphs = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                p = f'<p style="margin: 8px 0; line-height: 1.6;">{p}</p>'
            html_paragraphs.append(p)

        text = '\n'.join(html_paragraphs)

        # Single newlines to breaks (for non-HTML content)
        text = text.replace('\n', '<br>')

        return f"""
        <html>
        <body style="
            color: {c.text_primary};
            font-family: {Typography.BODY};
            font-size: 13px;
            line-height: 1.6;
        ">
            {text}
        </body>
        </html>
        """

    def _apply_styles(self) -> None:
        """Apply theme styles."""
        c = theme.colors

        if self._message_type == MessageType.USER:
            self.setStyleSheet(f"""
                #userBubble {{
                    background-color: {c.background_card};
                    border-radius: 12px;
                    border: 1px solid {c.border_light};
                }}
                #messageText {{
                    color: {c.text_primary};
                    font-family: {Typography.BODY};
                    font-size: 13px;
                    padding: 8px 12px;
                    background: transparent;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #aiBubble {{
                    background-color: transparent;
                    border-left: 3px solid {c.accent_primary};
                    padding-left: 12px;
                }}
                #aiLabel {{
                    color: {c.accent_primary};
                    font-family: {Typography.UI};
                }}
                #messageText {{
                    color: {c.text_primary};
                    font-family: {Typography.BODY};
                    font-size: 13px;
                    background: transparent;
                    border: none;
                }}
                #copyBtn {{
                    background-color: transparent;
                    color: {c.text_muted};
                    border: 1px solid {c.border_light};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                #copyBtn:hover {{
                    background-color: {c.background_canvas};
                    color: {c.text_secondary};
                }}
            """)

    def _on_copy_clicked(self) -> None:
        """Handle copy button click."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._text)

        # Show feedback
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy"))

        self.copyClicked.emit(self._text)

    def enterEvent(self, event) -> None:
        """Show copy button on hover for AI messages."""
        if self._message_type == MessageType.AI:
            self._copy_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Hide copy button when not hovering."""
        if self._message_type == MessageType.AI:
            self._copy_btn.hide()
        super().leaveEvent(event)

    def get_text(self) -> str:
        """Get the message text."""
        return self._text

    def get_message_type(self) -> MessageType:
        """Get the message type."""
        return self._message_type

    def get_citations(self) -> List[int]:
        """Get the citation page numbers."""
        return self._citations.copy()
