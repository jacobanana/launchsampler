"""UI Color Definitions - Single source of truth for all UI implementations.

This module defines the color scheme used across all UI implementations (TUI, LED UI).
Both UIs should synchronize their colors based on these definitions.

Color Scheme:
- Empty pads: Off (black)
- Assigned pads: Mode-specific colors (one_shot=red, toggle=orange, hold=blue, loop=green, loop_toggle=magenta)
- Playing pads: Yellow
- Selected pads (TUI only): Warning color
- MIDI-triggered pads (TUI only): Primary color

All colors are device-agnostic 8-bit RGB values. Device adapters handle
conversion to hardware-specific formats (e.g., 7-bit for MIDI, palette indices
for animations).
"""

from launchsampler.colors import COLORS
from launchsampler.models import Color, PlaybackMode

# Playback Mode Colors
# Maps each playback mode to its corresponding color
MODE_COLORS: dict[PlaybackMode, Color] = {
    PlaybackMode.ONE_SHOT: COLORS.RED,
    PlaybackMode.TOGGLE: COLORS.ORANGE,
    PlaybackMode.HOLD: COLORS.BLUE,
    PlaybackMode.LOOP: COLORS.GREEN,
    PlaybackMode.LOOP_TOGGLE: COLORS.MAGENTA,
}

# Playback State Colors
# These colors override mode colors when the pad is in a specific state

# Playing state (audio is currently playing)
PLAYING_COLOR = COLORS.YELLOW

# Empty pad (no sample assigned)
EMPTY_COLOR = COLORS.BLACK

# Panic button color (for emergency stop LED indicator)
PANIC_BUTTON_COLOR = COLORS.RED_DARK

# TUI-only states (not applicable to LED UI)

# Selected pad (TUI only - currently selected for editing)
SELECTED_TUI_CLASS = "selected"  # Uses $warning theme color in TUI

# MIDI triggered pad (TUI only - MIDI note is currently held down)
MIDI_ON_TUI_CLASS = "midi_on"  # Uses $primary theme color in TUI


def get_pad_color(pad, is_playing: bool = False) -> Color:
    """Get the color for a pad based on its state.

    This is the single source of truth for pad colors.
    Both TUI and LED UI use this function to determine colors.

    Args:
        pad: The Pad model
        is_playing: Whether the pad is currently playing audio

    Returns:
        Color: The 8-bit RGB color to display
    """
    # Playing state takes priority
    if is_playing:
        return PLAYING_COLOR

    # Assigned pad shows mode color
    if pad.is_assigned:
        return MODE_COLORS[pad.mode]

    # Empty pad is off
    return EMPTY_COLOR
