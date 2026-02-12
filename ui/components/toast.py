"""
Toast Notification System for DeepRead AI.

Non-intrusive notifications for user feedback with:
- Multiple severity levels (info, success, warning, error)
- Auto-dismiss after timeout
- Stacked notifications
"""

from enum import Enum
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon
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


class ToastSeverity(Enum):
    """Severity levels for toast notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Toast(QWidget):
    """
    Toast notification widget.

    A non-intrusive notification that auto-dismisses after a timeout.
    Supports multiple severity levels and can be stacked.

    Signals:
        dismissed(): Emitted when the toast is dismissed
        clicked(): Emitted when the toast is clicked
    """

    dismissed = Signal()
    clicked = Signal()

    # Icon SVGs (Lucide-style)
    ICONS = {
        ToastSeverity.INFO: """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>""",
        ToastSeverity.SUCCESS: """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>""",
        ToastSeverity.WARNING: """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>""",
        ToastSeverity.ERROR: """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>""",
    }

    # Toast colors by severity
    COLORS = {
        ToastSeverity.INFO: "#3b82f6",
        ToastSeverity.SUCCESS: "#10b981",
        ToastSeverity.WARNING: "#f59e0b",
        ToastSeverity.ERROR: "#ef4444",
    }

    # Active toasts for stacking
    _active_toasts: List["Toast"] = []
    _max_visible = 5
    _vertical_spacing = 8
    _margin_bottom = 24
    _margin_right = 24

    def __init__(
        self,
        message: str,
        severity: ToastSeverity = ToastSeverity.INFO,
        timeout: int = 4000,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self._message = message
        self._severity = severity
        self._timeout = timeout
        self._is_dismissing = False

        # Set up window properties
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Set up opacity effect for animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._setup_ui()
        self._apply_styles()

        # Auto-dismiss timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(12)

        # Icon label
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setText(self.ICONS.get(self._severity, ""))
        layout.addWidget(self._icon_label)

        # Message label
        self._message_label = QLabel(self._message, self)
        self._message_label.setWordWrap(True)
        self._message_label.setMaximumWidth(320)
        font = QFont()
        font.setPointSize(13)
        self._message_label.setFont(font)
        layout.addWidget(self._message_label, 1)

        # Close button
        self._close_btn = QPushButton("✕", self)
        self._close_btn.setObjectName("closeBtn")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.dismiss)
        layout.addWidget(self._close_btn)

        # Set fixed height based on content
        self.adjustSize()
        self.setFixedHeight(max(48, self.height()))

    def _apply_styles(self) -> None:
        """Apply theme styles."""
        c = theme.colors
        severity_color = self.COLORS.get(self._severity, c.info)

        self.setStyleSheet(f"""
            Toast {{
                background-color: rgba(30, 30, 30, 0.95);
                border-radius: 8px;
                border-left: 4px solid {severity_color};
            }}

            QLabel {{
                color: white;
                background: transparent;
                border: none;
            }}

            #message_label {{
                font-family: {Typography.UI};
            }}

            #closeBtn {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }}

            #closeBtn:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }}

            #closeBtn:pressed {{
                background-color: rgba(255, 255, 255, 0.2);
            }}
        """)

    def show(self) -> None:
        """Show the toast with animation."""
        # Position the toast
        self._position_toast()

        # Add to active toasts
        Toast._active_toasts.insert(0, self)

        # Limit visible toasts
        self._trim_toasts()

        # Show
        super().show()

        # Animate in
        self._animate_in()

        # Start dismiss timer
        self._dismiss_timer.start(self._timeout)

    def _position_toast(self) -> None:
        """Calculate and set the toast position."""
        screen = QApplication.primaryScreen().geometry()

        # Calculate position (bottom-right)
        x = screen.width() - self.width() - Toast._margin_right
        y = screen.height() - self.height() - Toast._margin_bottom

        # Adjust for existing toasts
        for toast in Toast._active_toasts:
            y -= toast.height() + Toast._vertical_spacing

        self.move(x, y)

    def _trim_toasts(self) -> None:
        """Remove excess toasts if over the limit."""
        while len(Toast._active_toasts) > Toast._max_visible:
            oldest = Toast._active_toasts[-1]
            oldest._dismiss_timer.stop()
            oldest.hide()
            oldest.deleteLater()
            Toast._active_toasts.remove(oldest)

    def _animate_in(self) -> None:
        """Animate the toast appearing."""
        self._anim_step = 0
        self._anim_steps = 8

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animation_step)
        self._anim_timer.start(16)

    def _animation_step(self) -> None:
        """Single animation step."""
        self._anim_step += 1
        progress = self._anim_step / self._anim_steps

        # Ease out
        ease = 1 - (1 - progress) ** 2

        self._opacity_effect.setOpacity(ease)

        if self._anim_step >= self._anim_steps:
            self._anim_timer.stop()
            self._opacity_effect.setOpacity(1.0)

    def _animate_out(self, callback) -> None:
        """Animate the toast disappearing."""
        self._anim_step = 0
        self._anim_steps = 6

        self._anim_timer = QTimer(self)

        def step():
            self._anim_step += 1
            progress = self._anim_step / self._anim_steps

            # Ease in
            ease = progress ** 2

            self._opacity_effect.setOpacity(1.0 - ease)

            if self._anim_step >= self._anim_steps:
                self._anim_timer.stop()
                callback()

        self._anim_timer.timeout.connect(step)
        self._anim_timer.start(16)

    def dismiss(self) -> None:
        """Dismiss the toast with animation."""
        if self._is_dismissing:
            return

        self._is_dismissing = True
        self._dismiss_timer.stop()

        # Animate out and cleanup
        def on_fade_complete():
            self.hide()
            if self in Toast._active_toasts:
                Toast._active_toasts.remove(self)
            self._reposition_toasts()
            self.dismissed.emit()
            self.deleteLater()

        self._animate_out(on_fade_complete)

    def _reposition_toasts(self) -> None:
        """Reposition all active toasts after one is removed."""
        screen = QApplication.primaryScreen().geometry()

        y = screen.height() - Toast._margin_bottom

        for toast in Toast._active_toasts:
            y -= toast.height() + Toast._vertical_spacing
            toast.move(screen.width() - toast.width() - Toast._margin_right, y)

    def mousePressEvent(self, event) -> None:
        """Handle click on the toast."""
        self.clicked.emit()
        # Don't dismiss on click, let user close manually or wait for timeout

    def enterEvent(self, event) -> None:
        """Pause auto-dismiss when hovering."""
        self._dismiss_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Resume auto-dismiss when not hovering."""
        self._dismiss_timer.start(2000)  # Give 2 more seconds
        super().leaveEvent(event)

    @classmethod
    def show_info(cls, message: str, timeout: int = 4000, parent=None) -> "Toast":
        """Show an info toast."""
        toast = cls(message, ToastSeverity.INFO, timeout, parent)
        toast.show()
        return toast

    @classmethod
    def show_success(cls, message: str, timeout: int = 4000, parent=None) -> "Toast":
        """Show a success toast."""
        toast = cls(message, ToastSeverity.SUCCESS, timeout, parent)
        toast.show()
        return toast

    @classmethod
    def show_warning(cls, message: str, timeout: int = 4000, parent=None) -> "Toast":
        """Show a warning toast."""
        toast = cls(message, ToastSeverity.WARNING, timeout, parent)
        toast.show()
        return toast

    @classmethod
    def show_error(cls, message: str, timeout: int = 6000, parent=None) -> "Toast":
        """Show an error toast."""
        toast = cls(message, ToastSeverity.ERROR, timeout, parent)
        toast.show()
        return toast

    @classmethod
    def dismiss_all(cls) -> None:
        """Dismiss all active toasts."""
        for toast in cls._active_toasts[:]:
            toast._dismiss_timer.stop()
            toast.hide()
            toast.deleteLater()
        cls._active_toasts.clear()
