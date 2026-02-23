# UI Improvements for Linux

This document describes the UI improvements made to DeepRead AI for better Linux compatibility and visual appeal.

## Changes Made

### 1. Font Stack (theme.py)
**Before:** Used "Segoe UI" which doesn't exist on Linux
**After:** Linux-optimized font stack:
- Cantarell (GNOME default)
- Ubuntu (Ubuntu default)
- Noto Sans (Google's universal font)
- Liberation Sans (Red Hat font, metric-compatible with Arial)
- DejaVu Sans (widely available on Linux)
- system-ui (generic system font)

### 2. Color Palette (theme.py)
- Changed to Google-style colors (better contrast on Linux displays)
- Warmer background tones (#f8f9fa instead of #f0f0f2)
- More saturated accent colors for better visibility
- Improved text contrast ratios

### 3. Visual Improvements

#### Scrollbars
- Wider (14px instead of 8px) for easier grabbing
- Visible track background
- Better hover states

#### Buttons
- Larger padding for touch-friendliness
- More visible borders on QToolButton
- Better focus indicators

#### Inputs
- Larger padding
- Better focus states with border changes
- Selection colors that match the theme

#### Splitter
- Thicker handle (3px instead of 1px)
- Pressed state added

#### Menus
- More padding for menu items
- Rounded corners
- Better disabled state styling

### 4. Icons (icons.py)
Created a new icon system using Unicode characters that work on Linux without external fonts:
- Navigation arrows (← → ↑ ↓)
- Actions (+ − × ✓)
- Document symbols (📄 📝 📂)
- AI symbols (● ✦ 💡)

### 5. PDF Viewer Navigation (viewer_widget.py)
- Changed text buttons to Unicode icons
- Added proper fonts for icon rendering
- Changed highlight buttons from letters (Y, G, B, P) to colored squares
- Removed "Highlight:" label for cleaner look
- Added keyboard shortcut hints in tooltips

### 6. Toolbar (main_window.py)
- Added icons to main toolbar buttons
- Added AI Panel toggle button directly in toolbar
- Button text changes based on state ("AI Panel" ↔ "Notes")

### 7. Chat Widget (chat_widget.py)
- Added send icon to button
- Improved styling with better padding and selection colors
- Added dot indicator to AI label

## Recommended Fonts for Best Experience

Install these fonts for the best visual experience:

```bash
# Ubuntu/Debian
sudo apt install fonts-cantarell fonts-noto-core fonts-dejavu-core

# Fedora
sudo dnf install cantarell-fonts google-noto-sans-fonts dejavu-sans-fonts

# Arch
sudo pacman -S cantarell-fonts noto-fonts ttf-dejavu
```

## Testing the UI

Run the application and verify:
1. Fonts render crisply (not blurry or fallback)
2. Icons display correctly (no boxes or missing characters)
3. Scrollbars are visible and usable
4. Buttons have proper hover/pressed states
5. Colors look balanced (not too washed out)

## Future Improvements

Potential future UI enhancements:
1. Add a proper icon font (like Phosphor or Material Symbols)
2. Implement a dark mode theme
3. Add animations for smoother transitions
4. Support for custom accent colors
5. High DPI display optimizations
