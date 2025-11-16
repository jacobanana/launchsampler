"""Launchpad output/LED control."""

from typing import List, Tuple, Optional
import logging
from launchsampler.models import Color
from launchsampler.devices.protocols import DeviceOutput
from launchsampler.midi import MidiManager
from .model import LaunchpadModel, LaunchpadInfo
from .mapper import LaunchpadNoteMapper
from .sysex import LaunchpadSysEx, LightingMode

logger = logging.getLogger(__name__)


class LaunchpadOutput(DeviceOutput):
    """Control Launchpad LED display."""

    def __init__(self, midi_manager: MidiManager, info: LaunchpadInfo):
        """
        Initialize Launchpad output controller.

        Args:
            midi_manager: MIDI manager for sending messages
            info: Launchpad device information
        """
        self.midi = midi_manager
        self.info = info
        self.mapper = LaunchpadNoteMapper(info.model)
        self.sysex = LaunchpadSysEx(info.model)
        self._initialized = False

    def initialize(self) -> None:
        """Enter programmer mode."""
        if self._initialized:
            logger.warning("LaunchpadOutput already initialized")
            return

        msg = self.sysex.programmer_mode(enable=True)
        if self.midi.send(msg):
            logger.info(f"Entered programmer mode ({self.info.model.display_name})")
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
        # Convert logical index to hardware note
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        # Build SysEx with RGB mode
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

        # Convert all indices to notes
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

        Flashes between off (black) and the specified color.

        Args:
            index: Logical pad index (0-63)
            color: Palette color index (0-127)
        """
        note = self.mapper.index_to_note(index)
        if note is None:
            logger.error(f"Invalid pad index: {index}")
            return

        # Flashing requires two colors: color_b (off state), color_a (on state)
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

    def clear_all(self) -> None:
        """Clear all LEDs (set to black)."""
        # Clear all 64 pads by iterating logical indices
        specs = []
        for index in range(64):
            note = self.mapper.index_to_note(index)
            if note is not None:
                specs.append((LightingMode.STATIC.value, note, 0))

        msg = self.sysex.led_lighting(specs)

        if not self.midi.send(msg):
            logger.warning("Failed to clear all LEDs")
