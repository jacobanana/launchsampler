"""UI Color Definitions - Single source of truth for all UI implementations.

This module defines the color scheme used across all UI implementations (TUI, LED UI).
Both UIs should synchronize their colors based on these definitions.

Color Scheme:
- Empty pads: Off (black)
- Assigned pads: Mode-specific colors (one_shot=red, loop=green, hold=blue, loop_toggle=magenta)
- Playing pads: Yellow
- Selected pads (TUI only): Warning color
- MIDI-triggered pads (TUI only): Primary color

The colors are defined using the LaunchpadColor enum, which contains both RGB values
and palette indices for all 128 Launchpad colors. CSS class names are automatically
derived from the PlaybackMode enum values.
"""

from typing import Dict

from launchsampler.models import Color, LaunchpadColor, PlaybackMode


# Playback Mode Colors
# Maps each playback mode to its corresponding LaunchpadColor
MODE_COLORS: Dict[PlaybackMode, LaunchpadColor] = {
    PlaybackMode.ONE_SHOT: LaunchpadColor.RED,
    PlaybackMode.LOOP: LaunchpadColor.GREEN,
    PlaybackMode.HOLD: LaunchpadColor.BLUE,
    PlaybackMode.LOOP_TOGGLE: LaunchpadColor.MAGENTA,
}

# Playback State Colors
# These colors override mode colors when the pad is in a specific state

# Playing state (audio is currently playing)
PLAYING_COLOR = LaunchpadColor.YELLOW

# Empty pad (no sample assigned)
EMPTY_COLOR = LaunchpadColor.BLACK

# TUI-only states (not applicable to LED UI)

# Selected pad (TUI only - currently selected for editing)
SELECTED_TUI_CLASS = "selected"  # Uses $warning theme color in TUI

# MIDI triggered pad (TUI only - MIDI note is currently held down)
MIDI_ON_TUI_CLASS = "midi_on"  # Uses $primary theme color in TUI


def get_pad_led_color(pad, is_playing: bool = False) -> Color:
    """Get the LED color for a pad based on its state.

    This is the single source of truth for LED colors.
    Both TUI (via CSS classes) and LED UI (via palette colors) should
    reflect the same color scheme.

    Args:
        pad: The Pad model
        is_playing: Whether the pad is currently playing audio

    Returns:
        Color: The RGB color to display
    """
    # Playing state takes priority
    if is_playing:
        return PLAYING_COLOR.rgb

    # Assigned pad shows mode color
    if pad.is_assigned:
        return MODE_COLORS[pad.mode].rgb

    # Empty pad is off
    return EMPTY_COLOR.rgb


def get_pad_led_palette_index(pad, is_playing: bool = False) -> int:
    """Get the Launchpad palette color index for a pad based on its state.

    This is for LED UI implementations that need palette indices.

    Args:
        pad: The Pad model
        is_playing: Whether the pad is currently playing audio

    Returns:
        int: Launchpad palette color index (0-127)
    """
    # Playing state takes priority
    if is_playing:
        return PLAYING_COLOR.palette

    # Assigned pad shows mode color
    if pad.is_assigned:
        return MODE_COLORS[pad.mode].palette

    # Empty pad is off
    return EMPTY_COLOR.palette

