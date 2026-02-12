"""
Theme management for DeepRead AI.

Cross-platform design with consistent appearance on Windows and Linux.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ThemeColors:
    """Color palette - Refined for Linux with better contrast and depth."""

    # Background colors - warmer, more sophisticated tones
    background_window: str = "#f8f9fa"      # Warm off-white
    background_paper: str = "#ffffff"       # Pure white
    background_canvas: str = "#f1f3f4"      # Subtle warm gray
    background_card: str = "#ffffff"        # White cards
    background_primary: str = "#ffffff"     # Alias
    background_secondary: str = "#f5f7f8"   # Alias
    background_tertiary: str = "#e8eaed"    # Darker gray with warmth

    # Text colors - improved contrast for Linux font rendering
    text_primary: str = "#202124"           # Near black (Google-style)
    text_secondary: str = "#5f6368"         # Medium gray
    text_muted: str = "#80868b"             # Light gray
    text_disabled: str = "#bdc1c6"          # Very light

    # Accent colors - deeper, more saturated for Linux displays
    accent_primary: str = "#1a73e8"         # Google Blue (better on Linux)
    accent_hover: str = "#4285f4"           # Lighter blue
    accent_pressed: str = "#1557b0"         # Darker blue
    accent_secondary: str = "#7c4dff"       # Deep purple
    accent_success: str = "#34a853"         # Google Green
    accent_warning: str = "#f9ab00"         # Google Amber

    # Status colors
    success: str = "#34a853"
    warning: str = "#f9ab00"
    error: str = "#ea4335"
    info: str = "#1a73e8"

    # Border colors - more visible on Linux
    border_light: str = "#dadce0"
    border_medium: str = "#bdc1c6"
    border_dark: str = "#5f6368"

    # Highlight colors - more saturated for better visibility
    highlight_yellow: str = "rgba(251, 188, 5, 0.35)"
    highlight_green: str = "rgba(52, 168, 83, 0.35)"
    highlight_blue: str = "rgba(26, 115, 232, 0.35)"
    highlight_pink: str = "rgba(234, 67, 53, 0.25)"


class Theme:
    """Theme manager for the application."""

    _instance: Optional["Theme"] = None

    def __new__(cls) -> "Theme":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._colors = ThemeColors()

    @property
    def colors(self) -> ThemeColors:
        """Get the current theme colors."""
        return self._colors

    def get_stylesheet(self) -> str:
        """Generate the application stylesheet optimized for Linux."""
        c = self._colors

        return f"""
        /* ===== BASE ===== */
        QMainWindow {{
            background-color: {c.background_window};
        }}

        QWidget {{
            font-family: "Cantarell", "Ubuntu", "Noto Sans", "Liberation Sans", "DejaVu Sans", system-ui, -apple-system, sans-serif;
            font-size: 14px;
            color: {c.text_primary};
        }}

        /* ===== TOOLBAR - Linux optimized with depth ===== */
        QToolBar {{
            background-color: {c.background_paper};
            border-bottom: 1px solid {c.border_light};
            padding: 10px 20px;
            spacing: 12px;
            min-height: 52px;
        }}

        /* ===== PUSH BUTTONS - Linux optimized with better depth ===== */
        QPushButton {{
            background-color: {c.accent_primary};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 13px;
            min-height: 32px;
        }}

        QPushButton:focus {{
            outline: none;
            border: 2px solid {c.accent_primary};
            background-color: {c.accent_pressed};
        }}

        QPushButton:hover {{
            background-color: {c.accent_hover};
        }}

        QPushButton:pressed {{
            background-color: {c.accent_pressed};
        }}

        QPushButton:disabled {{
            background-color: {c.border_light};
            color: {c.text_disabled};
        }}

        /* Secondary button style */
        QPushButton.secondary {{
            background-color: {c.background_paper};
            color: {c.text_primary};
            border: 1px solid {c.border_medium};
        }}

        QPushButton.secondary:hover {{
            background-color: {c.background_canvas};
            border-color: {c.border_dark};
        }}

        /* Tool buttons - Linux optimized with better visibility */
        QToolButton {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_light};
            border-radius: 6px;
            padding: 6px 12px;
            min-width: 32px;
            min-height: 32px;
            font-weight: 500;
        }}

        QToolButton:hover {{
            background-color: {c.background_canvas};
            border-color: {c.border_medium};
        }}

        QToolButton:pressed {{
            background-color: {c.background_tertiary};
            border-color: {c.border_dark};
        }}

        QToolButton:disabled {{
            background-color: {c.background_canvas};
            color: {c.text_disabled};
            border-color: {c.border_light};
        }}

        QToolButton:checked {{
            background-color: {c.accent_primary};
            color: white;
            border-color: {c.accent_primary};
        }}

        /* ===== INPUTS - Linux optimized ===== */
        QLineEdit {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_medium};
            border-radius: 8px;
            padding: 10px 14px;
            min-height: 24px;
            font-size: 14px;
            selection-background-color: {c.accent_primary};
            selection-color: white;
        }}

        QLineEdit:focus {{
            border: 2px solid {c.accent_primary};
            padding: 9px 13px;
        }}

        QLineEdit::placeholder {{
            color: {c.text_muted};
        }}

        QTextEdit {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_medium};
            border-radius: 8px;
            padding: 12px;
            font-size: 14px;
            selection-background-color: {c.accent_primary};
            selection-color: white;
        }}

        QTextEdit:focus {{
            border: 2px solid {c.accent_primary};
            padding: 11px;
        }}

        /* ===== SPINBOX - Linux optimized ===== */
        QSpinBox {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_medium};
            border-radius: 6px;
            padding: 8px;
            min-height: 24px;
            font-weight: 500;
        }}

        QSpinBox:focus {{
            border: 2px solid {c.accent_primary};
            padding: 7px;
        }}

        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: {c.background_canvas};
            border: 1px solid {c.border_light};
            width: 20px;
        }}

        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {c.background_tertiary};
        }}

        /* ===== SCROLL AREA ===== */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}

        /* ===== SCROLLBARS - Linux optimized, more visible ===== */
        QScrollBar:vertical {{
            background-color: {c.background_canvas};
            width: 14px;
            margin: 0px;
            border-radius: 7px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {c.border_medium};
            border-radius: 6px;
            min-height: 40px;
            margin: 3px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {c.border_dark};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {c.background_canvas};
            height: 14px;
            margin: 0px;
            border-radius: 7px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {c.border_medium};
            border-radius: 6px;
            min-width: 40px;
            margin: 3px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {c.border_dark};
        }}

        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* ===== SPLITTER - Linux optimized ===== */
        QSplitter::handle {{
            background-color: {c.border_light};
        }}

        QSplitter::handle:horizontal {{
            width: 3px;
        }}

        QSplitter::handle:vertical {{
            height: 3px;
        }}

        QSplitter::handle:hover {{
            background-color: {c.accent_primary};
        }}

        QSplitter::handle:pressed {{
            background-color: {c.accent_pressed};
        }}

        /* ===== LABELS ===== */
        QLabel {{
            color: {c.text_primary};
        }}

        /* ===== MENUS - Linux optimized ===== */
        QMenu {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_medium};
            border-radius: 8px;
            padding: 8px;
            margin: 4px;
        }}

        QMenu::item {{
            padding: 10px 24px;
            border-radius: 6px;
            font-size: 14px;
        }}

        QMenu::item:selected {{
            background-color: {c.accent_primary};
            color: white;
        }}

        QMenu::item:disabled {{
            color: {c.text_disabled};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {c.border_light};
            margin: 8px 12px;
        }}

        QMenuBar {{
            background-color: {c.background_paper};
            border-bottom: 1px solid {c.border_light};
            padding: 4px 8px;
        }}

        QMenuBar::item {{
            padding: 8px 16px;
            border-radius: 6px;
            background-color: transparent;
        }}

        QMenuBar::item:selected {{
            background-color: {c.background_canvas};
        }}

        QMenuBar::item:pressed {{
            background-color: {c.background_tertiary};
        }}

        /* ===== STATUS BAR - Linux optimized ===== */
        QStatusBar {{
            background-color: {c.background_paper};
            border-top: 1px solid {c.border_light};
            min-height: 32px;
            padding: 4px 16px;
        }}

        QStatusBar::item {{
            border: none;
        }}

        QStatusBar QLabel {{
            font-size: 13px;
            color: {c.text_secondary};
        }}

        /* ===== GROUP BOX - Linux optimized ===== */
        QGroupBox {{
            background-color: {c.background_paper};
            border: 1px solid {c.border_light};
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 16px;
            padding: 16px;
            font-weight: 600;
            font-size: 14px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
            color: {c.text_secondary};
        }}

        /* ===== TABS ===== */
        QTabWidget::pane {{
            border: none;
            background-color: transparent;
        }}

        QTabBar::tab {{
            background-color: transparent;
            border: none;
            padding: 8px 16px;
            margin-right: 4px;
            border-radius: 6px;
            color: {c.text_secondary};
        }}

        QTabBar::tab:selected {{
            background-color: {c.background_paper};
            color: {c.text_primary};
            font-weight: 500;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: rgba(0, 0, 0, 0.03);
        }}

        /* ===== LIST WIDGET ===== */
        QListWidget {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        QListWidget::item {{
            padding: 8px 12px;
            border-radius: 6px;
            margin: 2px 4px;
        }}

        QListWidget::item:selected {{
            background-color: {c.accent_primary};
            color: white;
        }}

        QListWidget::item:hover:!selected {{
            background-color: rgba(0, 0, 0, 0.03);
        }}

        /* ===== TOOLTIP ===== */
        QToolTip {{
            background-color: #2c2c2e;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }}
        """


# Typography constants - Linux optimized
class Typography:
    """Typography definitions optimized for Linux systems."""

    # Primary Linux font stack - prioritizes common Linux fonts
    DISPLAY = '"Cantarell", "Ubuntu", "Noto Sans", "Liberation Sans", "DejaVu Sans", system-ui, -apple-system, sans-serif'
    HEADING = '"Cantarell", "Ubuntu", "Noto Sans", "Liberation Sans", "DejaVu Sans", system-ui, -apple-system, sans-serif'
    BODY = '"Cantarell", "Ubuntu", "Noto Sans", "Liberation Sans", "DejaVu Sans", system-ui, -apple-system, sans-serif'
    UI = '"Cantarell", "Ubuntu", "Noto Sans", "Liberation Sans", "DejaVu Sans", system-ui, -apple-system, sans-serif'
    CODE = '"JetBrains Mono", "Fira Code", "Source Code Pro", "Ubuntu Mono", "DejaVu Sans Mono", "Liberation Mono", monospace'


# Shadow definitions
class Shadows:
    """Shadow definitions."""

    SMALL = "0 1px 2px rgba(0, 0, 0, 0.05)"
    MEDIUM = "0 2px 6px rgba(0, 0, 0, 0.08)"
    LARGE = "0 4px 12px rgba(0, 0, 0, 0.12)"
    XL = "0 8px 24px rgba(0, 0, 0, 0.16)"


# Animation timing
class Animation:
    """Animation timing functions."""

    FAST = "150ms ease-out"
    NORMAL = "250ms ease-out"
    SLOW = "350ms ease-out"

    EASE_OUT = "cubic-bezier(0.25, 1, 0.5, 1)"
    EASE_IN_OUT = "cubic-bezier(0.65, 0, 0.35, 1)"


# Global theme instance
theme = Theme()
