"""Launchpad MK3 family implementation (Pro, Mini, X)."""

import logging
from typing import Tuple, Optional, List
from launchsampler.models import Color
from launchsampler.devices.protocols import DeviceOutput
from launchsampler.midi import MidiManager
from launchsampler.devices.config import DeviceConfig
from .launchpad_sysex import LaunchpadSysEx, LightingMode

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

    def note_to_index(self, note: int) -> Optional[int]:
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

    def note_to_xy(self, note: int) -> Tuple[Optional[int], Optional[int]]:
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

    def index_to_note(self, index: int) -> Optional[int]:
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

    def xy_to_note(self, x: int, y: int) -> Optional[int]:
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
        Set single LED using logical index.

        Args:
            index: Logical pad index (0-63)
            color: RGB color (0-127 per channel)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        spec = (LightingMode.RGB.value, note, color.r, color.g, color.b)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} (note {note})")

    def set_leds_bulk(self, updates: List[Tuple[int, Color]]) -> None:
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
            logger.warning(f"Failed to set {len(specs)} LEDs in bulk")
        else:
            logger.debug(f"Set {len(specs)} LEDs in bulk")

    def set_led_flashing(self, index: int, color: int) -> None:
        """
        Set LED to flash using palette color.

        Args:
            index: Logical pad index (0-63)
            color: Palette color index (0-127)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        spec = (LightingMode.FLASHING.value, note, 0, color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} flashing (note {note})")

    def set_led_pulsing(self, index: int, color: int) -> None:
        """
        Set LED to pulse using palette color.

        Args:
            index: Logical pad index (0-63)
            color: Palette color index (0-127)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        spec = (LightingMode.PULSING.value, note, color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} pulsing (note {note})")

    def set_led_static(self, index: int, color: int) -> None:
        """
        Set LED to static palette color.

        Args:
            index: Logical pad index (0-63)
            color: Palette color index (0-127)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        spec = (LightingMode.STATIC.value, note, color)
        msg = self.sysex.led_lighting([spec])

        if not self.midi.send(msg):
            logger.warning(f"Failed to set LED {index} static (note {note})")

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
