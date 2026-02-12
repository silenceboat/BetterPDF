"""
Icon definitions using Unicode characters that render well on Linux.

These icons work without requiring any external icon fonts or images.
They use standard Unicode symbols that are supported by most Linux fonts
(DejaVu Sans, Noto Sans, Ubuntu, etc.)
"""


class Icons:
    """Unicode-based icons for use in the application."""

    # Navigation
    PREVIOUS = "←"
    NEXT = "→"
    UP = "↑"
    DOWN = "↓"
    FIRST = "⇤"
    LAST = "⇥"

    # Actions
    ADD = "+"
    REMOVE = "−"
    DELETE = "×"
    CLOSE = "✕"
    CHECK = "✓"
    EDIT = "✎"
    SAVE = "💾"
    OPEN = "📂"
    NEW = "📄"

    # View
    ZOOM_IN = "+"
    ZOOM_OUT = "−"
    FIT_WIDTH = "⤢"
    FULLSCREEN = "⛶"
    REFRESH = "↻"
    SEARCH = "🔍"

    # Media
    PLAY = "▶"
    PAUSE = "⏸"
    STOP = "⏹"

    # Document
    PDF = "📄"
    NOTE = "📝"
    HIGHLIGHT = "🖍"
    BOOKMARK = "🔖"
    FOLDER = "📁"

    # AI/Chat
    AI = "●"
    USER = "○"
    SEND = "➤"
    CHAT = "💬"
    SPARKLE = "✦"
    LIGHTBULB = "💡"

    # Status
    INFO = "ℹ"
    WARNING = "⚠"
    ERROR = "✕"
    SUCCESS = "✓"

    # Arrows
    EXPAND = "▾"
    COLLAPSE = "▴"
    MORE = "⋯"
    MENU = "☰"

    # Misc
    SETTINGS = "⚙"
    HELP = "?"
    LINK = "🔗"
    TIME = "🕐"
    CALENDAR = "📅"


# Font sizes for different icon contexts
class IconSize:
    """Recommended font sizes for icons."""

    SMALL = 10
    NORMAL = 12
    MEDIUM = 14
    LARGE = 16
    XL = 20


# Icon with styling helper
def get_icon_text(icon: str, size: int = IconSize.NORMAL, bold: bool = False) -> str:
    """
    Get HTML-formatted icon text for use in QLabel, QPushButton, etc.

    Args:
        icon: The icon character from Icons class
        size: Font size in points
        bold: Whether to make the icon bold

    Returns:
        HTML string for the styled icon
    """
    weight = "bold" if bold else "normal"
    return f'<span style="font-size: {size}pt; font-weight: {weight};">{icon}</span>'
