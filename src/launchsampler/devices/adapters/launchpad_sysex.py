"""Low-level SysEx message builder for Launchpad devices."""

from enum import Enum
from typing import List, Tuple, Optional
import mido


class LightingMode(Enum):
    """LED lighting modes."""
    STATIC = 0      # Static color from palette
    FLASHING = 1    # Flashing between two colors
    PULSING = 2     # Pulsing color
    RGB = 3         # Direct RGB color


class LaunchpadSysEx:
    """Low-level SysEx message builder for Launchpad devices."""

    def __init__(self, header: list[int]):
        """
        Initialize with SysEx header.

        Args:
            header: Raw SysEx header bytes
        """
        self.header = header
        self.model = None  # Kept for backwards compatibility

    @classmethod
    def from_header(cls, header: list[int]) -> 'LaunchpadSysEx':
        """
        Create LaunchpadSysEx from raw SysEx header.

        Args:
            header: Raw SysEx header bytes

        Returns:
            LaunchpadSysEx instance
        """
        return cls(header)

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
