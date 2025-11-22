"""
Launchpad MK3 family implementation (Pro, Mini, X).

Hardware-Specific Implementation
=================================

This module contains the device-specific "brains" for Launchpad MK3 devices.
It translates between logical pad indices and hardware MIDI notes, and builds
SysEx messages for LED control.

Mapper: Logical ↔ Hardware Translation
---------------------------------------

The LaunchpadMK3Mapper translates between logical indices and MIDI notes.

**Input Side (Button Press)**::

    Hardware Button Press → MIDI note 36
                                ↓
    LaunchpadMK3Mapper.note_to_index(36):
      offset = 11
      row_spacing = 10
      note_index = 36 - 11 = 25
      row = 25 // 10 = 2
      col = 25 % 10 = 5
      return row * 8 + col = 21
                                ↓
    Logical pad index 21

**Output Side (LED Control)**::

    Your code: set_pad_color(index=21, Color(255, 0, 0))
                                ↓
    LaunchpadMK3Mapper.index_to_note(21):
      row = 21 // 8 = 2
      col = 21 % 8 = 5
      note = 11 + (row * 10) + col
      return 11 + 20 + 5 = 36
                                ↓
    MIDI note 36
                                ↓
    LaunchpadSysEx.led_lighting([(RGB, 36, 255, 0, 0)])
                                ↓
    [0xF0, 0, 32, 41, 2, 14, 0x03, 3, 36, 255, 0, 0, 0xF7]
                                ↓
    Hardware LED turns RED

Hardware Layout
---------------

Launchpad MK3 in programmer mode uses this note layout::

    Row 7: 81 82 83 84 85 86 87 88    (top row)
    Row 6: 71 72 73 74 75 76 77 78
    Row 5: 61 62 63 64 65 66 67 68
    Row 4: 51 52 53 54 55 56 57 58
    Row 3: 41 42 43 44 45 46 47 48
    Row 2: 31 32 33 34 35 36 37 38
    Row 1: 21 22 23 24 25 26 27 28
    Row 0: 11 12 13 14 15 16 17 18    (bottom row)
           └─ bottom-left pad

Note the row spacing of 10 (includes gaps like 19, 29, etc.)

Key Design Decisions
--------------------

**Why separate Mapper from Output?**

- Mapper: Pure mathematical translation (no side effects)
- Output: Manages hardware state and sends MIDI messages

This separation makes testing trivial - you can verify note mapping
without needing actual hardware.

**Why store offset/spacing as constants?**

All MK3 devices (Pro, Mini, X) use the same programmer mode layout.
If Novation releases an MK4 with different layout, create a new mapper class.
"""

import logging

from launchsampler.devices.config import DeviceConfig
from launchsampler.devices.launchpad import LaunchpadPalette
from launchsampler.devices.launchpad.sysex import LaunchpadSysEx, LightingMode
from launchsampler.devices.protocols import DeviceOutput
from launchsampler.midi import MidiManager
from launchsampler.models import Color

logger = logging.getLogger(__name__)


class LaunchpadMK3Mapper:
    """
    Note mapper for Launchpad MK3 family devices.

    Maps between MIDI notes and logical pad indices/coordinates.
    All MK3 models (Pro, Mini, X) use the same note layout in programmer mode.
    """

    # Programmer mode layout
    # Bottom-left = note 11, bottom-right = note 18
    # Top-left = note 81, top-right = note 88
    # Row spacing = 10 (includes non-existent notes 19, 29, etc.)
    PROGRAMMER_MODE_OFFSET = 11
    PROGRAMMER_MODE_ROW_SPACING = 10

    def __init__(self, config: DeviceConfig):
        """
        Initialize note mapper.

        Args:
            config: Device configuration
        """
        self.config = config
        self.offset = self.PROGRAMMER_MODE_OFFSET
        self.row_spacing = self.PROGRAMMER_MODE_ROW_SPACING

    def note_to_index(self, note: int) -> int | None:
        """
        Convert MIDI note to logical pad index (0-63).

        Args:
            note: MIDI note number

        Returns:
            Pad index (0-63) or None if invalid note
        """
        x, y = self.note_to_xy(note)
        if x is None or y is None:
            return None

        return y * 8 + x

    def note_to_xy(self, note: int) -> tuple[int | None, int | None]:
        """
        Convert MIDI note to (x, y) coordinates.

        Args:
            note: MIDI note number

        Returns:
            (x, y) tuple or (None, None) if invalid
        """
        if note < self.offset or note > (self.offset + 7 * self.row_spacing + 7):
            return (None, None)

        adjusted = note - self.offset
        row = adjusted // self.row_spacing
        col = adjusted % self.row_spacing

        if col > 7 or row > 7:
            return (None, None)

        return (col, row)

    def index_to_note(self, index: int) -> int | None:
        """
        Convert logical pad index to MIDI note.

        Args:
            index: Pad index (0-63)

        Returns:
            MIDI note number or None if invalid index
        """
        if not 0 <= index < 64:
            return None

        row = index // 8
        col = index % 8

        return self.xy_to_note(col, row)

    def xy_to_note(self, x: int, y: int) -> int | None:
        """
        Convert (x, y) coordinates to MIDI note.

        Args:
            x: column (0-7)
            y: row (0-7)

        Returns:
            MIDI note number or None if invalid coordinates
        """
        if not (0 <= x < 8 and 0 <= y < 8):
            return None

        return self.offset + (y * self.row_spacing) + x


class LaunchpadMK3Output(DeviceOutput):
    """
    Output controller for Launchpad MK3 family.

    Handles LED control and device initialization for
    Launchpad Pro MK3, Mini MK3, and X models.
    """

    def __init__(self, midi_manager: MidiManager, config: DeviceConfig):
        """
        Initialize Launchpad MK3 output controller.

        Args:
            midi_manager: MIDI manager for sending messages
            config: Device configuration with SysEx header
        """
        self.midi = midi_manager
        self.config = config
        self.mapper = LaunchpadMK3Mapper(config)
        if config.sysex_header is None:
            raise ValueError("sysex_header is required for LaunchpadMK3")
        self.sysex = LaunchpadSysEx.from_header(config.sysex_header)
        self._initialized = False

    def initialize(self) -> None:
        """Enter programmer mode."""
        if self._initialized:
            logger.warning(f"{self.config.model} already initialized")
            return

        msg = self.sysex.programmer_mode(enable=True)
        if self.midi.send(msg):
            logger.info(f"Entered programmer mode ({self.config.model})")
            self._initialized = True
        else:
            logger.error("Failed to enter programmer mode")

    def shutdown(self) -> None:
        """Exit programmer mode and clear LEDs."""
        if not self._initialized:
            return

        self.clear_all()

        msg = self.sysex.programmer_mode(enable=False)
        if self.midi.send(msg):
            logger.info("Exited programmer mode")
            self._initialized = False
        else:
            logger.error("Failed to exit programmer mode")

    def set_led(self, index: int, color: Color) -> None:
        """
        Set single LED color.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (each channel 0-127)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        spec = (LightingMode.RGB.value, note, color.r, color.g, color.b)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} (note {note})")

    def set_leds(self, updates: list[tuple[int, Color]]) -> None:
        """
        Set multiple LEDs efficiently.

        Args:
            updates: List of (logical_index, color) tuples
        """
        if not updates:
            return

        specs = []
        for index, color in updates:
            note = self.mapper.index_to_note(index)
            if note is None:
                logger.warning(f"Skipping invalid pad index: {index}")
                continue
            specs.append((LightingMode.RGB.value, note, color.r, color.g, color.b))

        if not specs:
            return

        msg = self.sysex.led_lighting(specs)

        if not self.midi.send(msg):
            logger.warning(f"Failed to set {len(specs)} LEDs")
        else:
            logger.debug(f"Set {len(specs)} LEDs")

    def set_led_flashing(self, index: int, color: Color) -> None:
        """
        Set LED to flash/blink animation.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (converted to nearest palette color)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        palette_color = LaunchpadPalette.from_color(color)
        spec = (LightingMode.FLASHING.value, note, 0, palette_color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} flashing (note {note})")

    def set_led_pulsing(self, index: int, color: Color) -> None:
        """
        Set LED to pulse/breathe animation.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (converted to nearest palette color)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        palette_color = LaunchpadPalette.from_color(color)
        spec = (LightingMode.PULSING.value, note, palette_color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} pulsing (note {note})")

    def set_control_led(self, cc_number: int, color: Color) -> None:
        """
        Set LED for control button using RGB color.

        Args:
            cc_number: MIDI CC control number
            color: RGB color (0-127 per channel)
        """
        spec = (LightingMode.RGB.value, cc_number, color.r, color.g, color.b)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set control LED for CC {cc_number}")
        else:
            logger.debug(f"Set control LED for CC {cc_number}")

    def set_control_led_static(self, cc_number: int, palette_color: int) -> None:
        """
        Set LED for control button using palette color.

        Args:
            cc_number: MIDI CC control number
            palette_color: Palette color index (0-127)
        """
        spec = (LightingMode.STATIC.value, cc_number, palette_color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set control LED for CC {cc_number}")
        else:
            logger.debug(f"Set control LED for CC {cc_number} to palette {palette_color}")

    def clear_all(self) -> None:
        """Clear all LEDs (set to black)."""
        specs = []
        for index in range(64):
            note = self.mapper.index_to_note(index)
            if note is not None:
                specs.append((LightingMode.STATIC.value, note, 0))

        msg = self.sysex.led_lighting(specs)

        if not self.midi.send(msg):
            logger.warning("Failed to clear all LEDs")
