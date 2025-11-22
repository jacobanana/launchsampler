"""Shared UI infrastructure for all UI implementations.

This package contains shared components used by both TUI and LED UI:
- colors: Color definitions and color scheme logic
- adapter: UIAdapter protocol for UI lifecycle management
"""

from .adapter import UIAdapter
from .colors import (
    EMPTY_COLOR,
    MIDI_ON_TUI_CLASS,
    MODE_COLORS,
    PANIC_BUTTON_COLOR,
    PLAYING_COLOR,
    SELECTED_TUI_CLASS,
    get_pad_color,
)

__all__ = [
    "EMPTY_COLOR",
    "MIDI_ON_TUI_CLASS",
    # Colors
    "MODE_COLORS",
    "PANIC_BUTTON_COLOR",
    "PLAYING_COLOR",
    "SELECTED_TUI_CLASS",
    # Adapter
    "UIAdapter",
    "get_pad_color",
]
