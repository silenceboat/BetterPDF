"""
AI Chat Panel Widget for DeepRead AI.

The main AI conversation panel with:
- Message history with scrollable area
- Quick action buttons at top (Full Summary, Key Points, etc.)
- Input area at bottom with send button
- Typing indicator for AI responses
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..styles.theme import theme, Typography
from ..styles.icons import Icons
from .message_bubble import MessageBubble, MessageType


class TypingIndicator(QWidget):
    """
    Animated typing indicator for AI responses.

    Shows three animated dots to indicate the AI is typing.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._dot_index = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # AI label with icon
        ai_label = QLabel("● AI", self)
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Bold)
        ai_label.setFont(font)
        ai_label.setStyleSheet(f"color: {theme.colors.accent_primary};")
        layout.addWidget(ai_label)

        layout.addSpacing(8)

        # Dots
        self._dots = []
        for i in range(3):
            dot = QLabel("●", self)
            dot.setStyleSheet(f"color: {theme.colors.border_medium};")
            self._dots.append(dot)
            layout.addWidget(dot)

        layout.addStretch()

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(400)

        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply theme styles."""
        self.setStyleSheet(f"""
            TypingIndicator {{
                background-color: transparent;
                border-left: 3px solid {theme.colors.accent_primary};
            }}
        """)

    def _animate(self) -> None:
        """Animate the dots."""
        c = theme.colors
        for i, dot in enumerate(self._dots):
            if i == self._dot_index:
                dot.setStyleSheet(f"color: {c.accent_primary};")
            else:
                dot.setStyleSheet(f"color: {c.border_medium};")

        self._dot_index = (self._dot_index + 1) % 3

    def stop(self) -> None:
        """Stop the animation."""
        self._timer.stop()


class AIChatWidget(QWidget):
    """
    Main AI chat panel widget.

    Provides a chat interface for interacting with the AI about the document.

    Signals:
        messageSent(str): Emitted when user sends a message
        quickActionTriggered(str): Emitted when a quick action button is clicked
        citationClicked(int): Emitted when a citation pill is clicked
    """

    messageSent = Signal(str)
    quickActionTriggered = Signal(str)
    citationClicked = Signal(int)

    # Quick action definitions
    QUICK_ACTIONS = [
        ("Full Summary", "Generate a comprehensive summary of the document"),
        ("Key Points", "Extract the main key points from the document"),
        ("Questions", "Generate study questions about the content"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._messages: List[MessageBubble] = []
        self._is_typing = False

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Quick actions bar
        self._quick_actions_widget = self._create_quick_actions()
        layout.addWidget(self._quick_actions_widget)

        # Messages scroll area
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        # Messages container
        self._messages_container = QWidget(self._scroll_area)
        self._messages_container.setObjectName("messagesContainer")
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 16, 16, 16)
        self._messages_layout.setSpacing(16)
        self._messages_layout.addStretch()

        self._scroll_area.setWidget(self._messages_container)
        layout.addWidget(self._scroll_area, 1)

        # Typing indicator (hidden by default)
        self._typing_indicator = TypingIndicator(self._messages_container)
        self._typing_indicator.hide()
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, self._typing_indicator
        )

        # Input area
        self._input_widget = self._create_input_area()
        layout.addWidget(self._input_widget)

    def _create_quick_actions(self) -> QWidget:
        """Create the quick actions bar."""
        widget = QWidget(self)
        widget.setObjectName("quickActions")
        widget.setFixedHeight(56)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Quick Actions:", widget)
        title.setObjectName("quickActionsTitle")
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Medium)
        title.setFont(font)
        layout.addWidget(title)

        layout.addSpacing(8)

        # Action buttons
        self._quick_action_buttons = []
        for label, tooltip in self.QUICK_ACTIONS:
            btn = QPushButton(label, widget)
            btn.setObjectName("quickActionBtn")
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.clicked.connect(
                lambda checked, l=label: self._on_quick_action_clicked(l)
            )
            self._quick_action_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        return widget

    def _create_input_area(self) -> QWidget:
        """Create the input area at the bottom."""
        widget = QWidget(self)
        widget.setObjectName("inputArea")
        widget.setFixedHeight(72)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Input field
        self._input_field = QLineEdit(widget)
        self._input_field.setObjectName("chatInput")
        self._input_field.setPlaceholderText("Ask about this document...")
        self._input_field.returnPressed.connect(self._on_send_clicked)
        layout.addWidget(self._input_field, 1)

        # Send button with icon
        self._send_btn = QPushButton(f"{Icons.SEND} Send", widget)
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFixedSize(80, 40)
        self._send_btn.clicked.connect(self._on_send_clicked)
        layout.addWidget(self._send_btn)

        return widget

    def _apply_styles(self) -> None:
        """Apply theme styles optimized for Linux."""
        c = theme.colors

        self.setStyleSheet(f"""
            AIChatWidget {{
                background-color: {c.background_canvas};
            }}

            #quickActions {{
                background-color: {c.background_paper};
                border-bottom: 1px solid {c.border_light};
            }}

            #quickActionsTitle {{
                color: {c.text_secondary};
                font-family: {Typography.UI};
                font-weight: 600;
            }}

            #quickActionBtn {{
                background-color: {c.background_card};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }}

            #quickActionBtn:hover {{
                background-color: {c.background_canvas};
                border-color: {c.border_medium};
            }}

            #quickActionBtn:pressed {{
                background-color: {c.background_tertiary};
            }}

            #messagesContainer {{
                background-color: {c.background_canvas};
            }}

            #inputArea {{
                background-color: {c.background_paper};
                border-top: 1px solid {c.border_light};
            }}

            #chatInput {{
                background-color: {c.background_card};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 14px;
                font-family: {Typography.BODY};
                selection-background-color: {c.accent_primary};
                selection-color: white;
            }}

            #chatInput:focus {{
                border: 2px solid {c.accent_primary};
                padding: 9px 17px;
            }}

            #chatInput::placeholder {{
                color: {c.text_muted};
            }}

            #sendBtn {{
                background-color: {c.accent_primary};
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 600;
                font-size: 13px;
                padding: 0 16px;
            }}

            #sendBtn:hover {{
                background-color: {c.accent_hover};
            }}

            #sendBtn:pressed {{
                background-color: {c.accent_pressed};
            }}

            #sendBtn:disabled {{
                background-color: {c.border_medium};
                color: {c.text_disabled};
            }}
        """)

    def _on_send_clicked(self) -> None:
        """Handle send button click."""
        text = self._input_field.text().strip()
        if text:
            self.add_user_message(text)
            self.messageSent.emit(text)
            self._input_field.clear()

    def _on_quick_action_clicked(self, action: str) -> None:
        """Handle quick action button click."""
        self.quickActionTriggered.emit(action)

    def _scroll_to_bottom(self) -> None:
        """Scroll the messages area to the bottom."""
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def add_user_message(self, text: str) -> None:
        """
        Add a user message to the chat.

        Args:
            text: The message text
        """
        bubble = MessageBubble(MessageType.USER, text, parent=self._messages_container)

        # Insert before the stretch and typing indicator
        index = self._messages_layout.count() - 2
        if self._typing_indicator.isVisible():
            index -= 1

        self._messages_layout.insertWidget(index, bubble)
        self._messages.append(bubble)

        QTimer.singleShot(50, self._scroll_to_bottom)

    def add_ai_message(
        self,
        text: str,
        citations: Optional[List[int]] = None,
        show_typing: bool = True
    ) -> None:
        """
        Add an AI message to the chat.

        Args:
            text: The message text
            citations: Optional list of page numbers for citations
            show_typing: Whether to show typing indicator first
        """
        if show_typing:
            self.show_typing_indicator()

            # Delay the actual message
            QTimer.singleShot(1000, lambda: self._add_ai_message_now(text, citations))
        else:
            self._add_ai_message_now(text, citations)

    def _add_ai_message_now(self, text: str, citations: Optional[List[int]]) -> None:
        """Add the AI message now (after typing delay)."""
        self.hide_typing_indicator()

        bubble = MessageBubble(
            MessageType.AI, text, citations, parent=self._messages_container
        )
        bubble.citationClicked.connect(self.citationClicked.emit)

        # Insert before the stretch
        index = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(index, bubble)
        self._messages.append(bubble)

        QTimer.singleShot(50, self._scroll_to_bottom)

    def show_typing_indicator(self) -> None:
        """Show the typing indicator."""
        self._is_typing = True
        self._typing_indicator.show()
        QTimer.singleShot(50, self._scroll_to_bottom)

    def hide_typing_indicator(self) -> None:
        """Hide the typing indicator."""
        self._is_typing = False
        self._typing_indicator.hide()

    def clear_chat(self) -> None:
        """Clear all messages from the chat."""
        for bubble in self._messages:
            bubble.deleteLater()
        self._messages.clear()
        self.hide_typing_indicator()

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable the input area."""
        self._input_field.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def set_quick_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable quick action buttons."""
        for btn in self._quick_action_buttons:
            btn.setEnabled(enabled)

    def get_messages(self) -> List[MessageBubble]:
        """Get all message bubbles."""
        return self._messages.copy()

    def is_typing(self) -> bool:
        """Check if the AI is currently showing typing indicator."""
        return self._is_typing
