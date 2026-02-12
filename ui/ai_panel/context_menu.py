
"""
AI Context Menu for DeepRead AI.

A contextual popup that appears when text is selected in the PDF,
offering AI-powered actions like Explain, Translate, Summarize, etc.
"""

from enum import Enum
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..styles.theme import theme, Typography


class AIAction(Enum):
    """Available AI actions for selected text."""
    EXPLAIN = "explain"
    TRANSLATE = "translate"
    SUMMARIZE = "summarize"
    DEFINE = "define"
    ASK_AI = "ask_ai"


class AIContextMenu(QWidget):
    """
    Context menu widget for AI actions on selected text.

    This widget appears near text selection and provides quick access
    to AI-powered actions. It uses a custom widget (not native menu)
    for full styling control.

    Signals:
        actionTriggered(AIAction, str): Emitted when an action is clicked
            - AIAction: The action type
            - str: The selected text
        dismissed(): Emitted when the menu is dismissed
    """

    actionTriggered = Signal(object, str)  # AIAction, text
    dismissed = Signal()

    # SVG Icons as strings (Lucide-style)
    ICONS = {
        AIAction.EXPLAIN: """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>""",
        AIAction.TRANSLATE: """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg>""",
        AIAction.SUMMARIZE: """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="21" y1="10" x2="3" y2="10"/><line x1="21" y1="6" x2="3" y2="6"/><line x1="21" y1="14" x2="3" y2="14"/><line x1="21" y1="18" x2="3" y2="18"/></svg>""",
        AIAction.DEFINE: """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>""",
        AIAction.ASK_AI: """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>""",
    }

    ACTION_LABELS = {
        AIAction.EXPLAIN: "Explain",
        AIAction.TRANSLATE: "Translate",
        AIAction.SUMMARIZE: "Summarize",
        AIAction.DEFINE: "Define",
        AIAction.ASK_AI: "Ask AI",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._selected_text = ""
        self._selection_rect = QRect()
        self._animation_opacity = 0.0
        self._animation_scale = 0.95

        # Set up window properties
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Set up opacity effect for animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._setup_ui()
        self._apply_styles()

        # Auto-hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_menu)

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container widget for styling
        self._container = QWidget(self)
        self._container.setObjectName("contextMenuContainer")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(8)

        # Quick actions row
        self._actions_widget = QWidget(self._container)
        actions_layout = QHBoxLayout(self._actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)

        # Create action buttons
        self._action_buttons = {}
        for action in AIAction:
            btn = self._create_action_button(action)
            self._action_buttons[action] = btn
            actions_layout.addWidget(btn)

        actions_layout.addStretch()
        container_layout.addWidget(self._actions_widget)

        # Selected text preview (truncated)
        self._preview_label = QLabel(self._container)
        self._preview_label.setObjectName("previewLabel")
        self._preview_label.setWordWrap(True)
        self._preview_label.setMaximumWidth(300)
        self._preview_label.hide()
        container_layout.addWidget(self._preview_label)

        main_layout.addWidget(self._container)

        # Set fixed height
        self.setFixedHeight(70)

    def _create_action_button(self, action: AIAction) -> QPushButton:
        """Create an action button with icon and label."""
        btn = QPushButton(self.ACTION_LABELS[action], self._actions_widget)
        btn.setObjectName(f"actionBtn_{action.value}")
        btn.setProperty("action", action.value)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(36)
        btn.clicked.connect(lambda: self._on_action_clicked(action))
        return btn

    def _apply_styles(self) -> None:
        """Apply the theme styles."""
        c = theme.colors

        self.setStyleSheet(f"""
            #contextMenuContainer {{
                background-color: {c.background_card};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }}

            QPushButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                font-family: {Typography.UI};
            }}

            QPushButton:hover {{
                background-color: {c.background_canvas};
                color: {c.accent_primary};
            }}

            QPushButton:pressed {{
                background-color: {c.border_light};
            }}

            #previewLabel {{
                color: {c.text_muted};
                font-size: 11px;
                font-style: italic;
                padding: 4px 8px;
                background-color: {c.background_canvas};
                border-radius: 4px;
            }}
        """)

    def show_at_selection(self, text: str, rect: QRect, parent_widget: QWidget) -> None:
        """
        Show the context menu near the selected text.

        Args:
            text: The selected text
            rect: The selection rectangle in screen coordinates
            parent_widget: The parent widget to position relative to
        """
        self._selected_text = text
        self._selection_rect = rect

        # Update preview text
        preview = text[:100] + "..." if len(text) > 100 else text
        self._preview_label.setText(f'"{preview}"')

        # Calculate position
        pos = self._calculate_position(rect, parent_widget)
        self.move(pos)

        # Show with animation
        self.show()
        self._animate_in()

        # Start auto-hide timer (10 seconds)
        self._hide_timer.start(10000)

    def _calculate_position(self, rect: QRect, parent_widget: QWidget) -> QPoint:
        """
        Calculate the menu position based on selection rect.

        Tries to position below the selection, but will position above
        if there's not enough room.
        """
        # Get screen geometry
        screen = QApplication.primaryScreen().geometry()

        # Default: position below selection
        x = rect.center().x() - self.width() // 2
        y = rect.bottom() + 8

        # Ensure horizontal bounds
        if x < 10:
            x = 10
        elif x + self.width() > screen.width() - 10:
            x = screen.width() - self.width() - 10

        # Check vertical bounds - if not enough room below, position above
        if y + self.height() > screen.height() - 10:
            y = rect.top() - self.height() - 8
            if y < 10:
                y = 10

        return QPoint(x, y)

    def _animate_in(self) -> None:
        """Animate the menu appearing."""
        self._animation_opacity = 0.0
        self._animation_scale = 0.95

        # Simple animation using timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animation_step)
        self._anim_timer.start(16)  # ~60fps

        self._anim_step = 0
        self._anim_steps = 10  # 150ms total

    def _animation_step(self) -> None:
        """Single animation step."""
        self._anim_step += 1
        progress = self._anim_step / self._anim_steps

        # Ease out
        ease = 1 - (1 - progress) ** 2

        self._animation_opacity = ease
        self._animation_scale = 0.95 + 0.05 * ease

        self._opacity_effect.setOpacity(self._animation_opacity)

        if self._anim_step >= self._anim_steps:
            self._anim_timer.stop()
            self._opacity_effect.setOpacity(1.0)

    def _on_action_clicked(self, action: AIAction) -> None:
        """Handle action button click."""
        self.actionTriggered.emit(action, self._selected_text)
        self.hide_menu()

    def hide_menu(self) -> None:
        """Hide the menu with animation."""
        self._hide_timer.stop()
        self.hide()
        self.dismissed.emit()

    def get_selected_text(self) -> str:
        """Get the currently selected text."""
        return self._selected_text

    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom paint for shadow effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw shadow
        shadow_color = QColor(0, 0, 0, 30)
        painter.fillRect(
            self.rect().adjusted(2, 4, -2, -2),
            shadow_color
        )

        super().paintEvent(event)

    def enterEvent(self, event) -> None:
        """Pause auto-hide when mouse enters."""
        self._hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Resume auto-hide when mouse leaves."""
        self._hide_timer.start(3000)  # Hide after 3 seconds of no interaction
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        """Handle escape key to dismiss."""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_menu()
        else:
            super().keyPressEvent(event)
