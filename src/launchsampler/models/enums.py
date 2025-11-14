"""Enumerations for the Launchpad sampler."""

from enum import Enum
from .color import Color

class PlaybackMode(str, Enum):
    """Audio playback modes."""

    ONE_SHOT = "one_shot"  # Play once, stop
    LOOP = "loop"          # Loop continuously
    HOLD = "hold"          # Play while held, stop on release
    LOOP_TOGGLE = "loop_toggle"  # Toggle looping on/off with note on messages

    def get_default_color(self) -> Color:
        """Get default LED color for this playback mode.

        Returns:
            Color: Default color (Red for ONE_SHOT, Green for LOOP, Blue for HOLD, Magenta for LOOP_TOGGLE)
        """

        return {
            PlaybackMode.ONE_SHOT: Color(r=127, g=0, b=0),  # Red
            PlaybackMode.LOOP: Color(r=0, g=127, b=0),      # Green
            PlaybackMode.HOLD: Color(r=0, g=0, b=127),      # Blue
            PlaybackMode.LOOP_TOGGLE: Color(r=127, g=0, b=127),  # Magenta
        }[self]
