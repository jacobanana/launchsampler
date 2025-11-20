"""Shared UI infrastructure for all UI implementations.

This package contains shared components used by both TUI and LED UI:
- colors: Color definitions and color scheme logic
- adapter: UIAdapter protocol for UI lifecycle management
"""

from .colors import (
    MODE_COLORS,
    PLAYING_COLOR,
    EMPTY_COLOR,
    PANIC_BUTTON_COLOR,
    SELECTED_TUI_CLASS,
    MIDI_ON_TUI_CLASS,
    get_pad_led_color,
    get_pad_led_palette_index,
)
from .adapter import UIAdapter

__all__ = [
    # Colors
    "MODE_COLORS",
    "PLAYING_COLOR",
    "EMPTY_COLOR",
    "PANIC_BUTTON_COLOR",
    "SELECTED_TUI_CLASS",
    "MIDI_ON_TUI_CLASS",
    "get_pad_led_color",
    "get_pad_led_palette_index",
    # Adapter
    "UIAdapter",
]
