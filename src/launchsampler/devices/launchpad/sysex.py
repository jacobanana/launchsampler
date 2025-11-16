"""Low-level SysEx message builder for Launchpad devices."""

from enum import Enum
from typing import List, Tuple
import mido
from .model import LaunchpadModel


class LightingMode(Enum):
    """LED lighting modes."""
    STATIC = 0      # Static color from palette
    FLASHING = 1    # Flashing between two colors
    PULSING = 2     # Pulsing color
    RGB = 3         # Direct RGB color


class LaunchpadSysEx:
    """Low-level SysEx message builder for Launchpad devices."""

    def __init__(self, model: LaunchpadModel):
        self.model = model
        self.header = model.sysex_header

    def programmer_mode(self, enable: bool) -> mido.Message:
        """Build programmer mode toggle message."""
        data = self.header + [0x0E, 0x01 if enable else 0x00]
        return mido.Message('sysex', data=data)

    def led_lighting(self, specs: List[Tuple]) -> mido.Message:
        """
        Build LED lighting SysEx message.

        Args:
            specs: List of (lighting_type, led_note, *data_bytes)
                   NOTE: led_note is hardware MIDI note, not logical index
        """
        data = self.header + [0x03]
        for spec in specs:
            data.extend(spec)
        return mido.Message('sysex', data=data)
