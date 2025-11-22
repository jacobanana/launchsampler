"""
Low-level SysEx message builder for Launchpad devices.

SysEx: The Launchpad's Secret Language
=======================================

This module builds System Exclusive (SysEx) MIDI messages that control
Launchpad hardware features like LED colors and device modes.

What is SysEx?
--------------

SysEx messages are manufacturer-specific MIDI messages that allow control
beyond standard MIDI. They follow this format::

    [0xF0] [Manufacturer ID] [Device-specific data...] [0xF7]
     Start                                              End

For Novation Launchpad devices::

    [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, ...]
     │     └──────┬──────┘  │    └─ Model ID (0x0E = MK3)
     │         Novation      └─ SysEx command type
     Start of SysEx

LED Lighting Message Flow
--------------------------

::

    Your code calls:
    set_pad_color(index=21, Color(255, 0, 0))
          ↓
    LaunchpadMK3Output.set_led(21, color):
      note = mapper.index_to_note(21)  # Returns 36
      sysex = LaunchpadSysEx.led_lighting([
        (RGB, 36, 255, 0, 0)
      ])
          ↓
    LaunchpadSysEx.led_lighting(...):
      Build message:
        header = [0x00, 0x20, 0x29, 0x02, 0x0E]
        command = 0x03  (LED lighting command)
        data = [3, 36, 255, 0, 0]
               │  │   └─── RGB values
               │  └─ MIDI note (hardware-specific)
               └─ Lighting mode (3 = RGB)
          ↓
    Complete SysEx message:
    [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x03, 3, 36, 255, 0, 0, 0xF7]
          ↓
    Sent via MIDI output
          ↓
    Hardware LED turns RED

SysEx Commands
--------------

The Launchpad MK3 supports these SysEx commands:

- **0x03**: LED Lighting (set LED colors)
- **0x0E**: Programmer Mode (enable/disable custom mode)

Lighting Modes
--------------

When setting LED colors, you can use different modes:

- **STATIC (0)**: Use a color from the device palette (0-127)
- **FLASHING (1)**: Flash between two palette colors
- **PULSING (2)**: Pulse a palette color
- **RGB (3)**: Direct RGB color (most common, used by this implementation)

Example RGB Message
-------------------

To light pad at MIDI note 36 with red color::

    Data: [3, 36, 255, 0, 0]
           │  │   │   │  │
           │  │   │   │  └─ Blue: 0
           │  │   │   └─ Green: 0
           │  │   └─ Red: 255
           │  └─ MIDI note: 36
           └─ Mode: RGB (3)

You can send multiple LED specs in one message::

    led_lighting([
        (RGB, 36, 255, 0, 0),    # Note 36: Red
        (RGB, 37, 0, 255, 0),    # Note 37: Green
        (RGB, 38, 0, 0, 255),    # Note 38: Blue
    ])

This is more efficient than sending three separate messages.

Key Design Principle
--------------------

**Hardware abstraction boundary**: This module is the LOWEST level of
hardware interaction. It knows about MIDI notes (not logical indices)
and SysEx byte sequences (not Color objects).

The layer above (LaunchpadMK3Output) handles the translation from
high-level concepts to low-level bytes.

References
----------

- Launchpad Pro MK3 Programmer's Reference Manual
- MIDI System Exclusive specification
"""

from enum import Enum

import mido


class LightingMode(Enum):
    """LED lighting modes."""

    STATIC = 0  # Static color from palette
    FLASHING = 1  # Flashing between two colors
    PULSING = 2  # Pulsing color
    RGB = 3  # Direct RGB color


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
    def from_header(cls, header: list[int]) -> "LaunchpadSysEx":
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
        data = [*self.header, 14, 1 if enable else 0]
        return mido.Message("sysex", data=data)

    def led_lighting(self, specs: list[tuple]) -> mido.Message:
        """
        Build LED lighting SysEx message.

        Args:
            specs: List of (lighting_type, led_note, *data_bytes)
                   NOTE: led_note is hardware MIDI note, not logical index
        """
        data = [*self.header, LightingMode.RGB.value]
        for spec in specs:
            data.extend(spec)
        return mido.Message("sysex", data=data)
