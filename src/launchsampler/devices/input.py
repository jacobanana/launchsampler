"""Generic MIDI input parsing for all devices."""

from typing import Optional, Protocol
import mido
from .protocols import DeviceInput, DeviceEvent, PadPressEvent, PadReleaseEvent, ControlChangeEvent


class NoteMapper(Protocol):
    """Protocol for device-specific note mapping."""

    def note_to_index(self, note: int) -> Optional[int]:
        """Convert hardware MIDI note to logical pad index."""
        ...

    def index_to_note(self, index: int) -> int:
        """Convert logical pad index to hardware MIDI note."""
        ...


class GenericInput(DeviceInput):
    """
    Generic MIDI input parser.

    Handles standard MIDI messages (note_on, note_off, control_change)
    and delegates hardware-specific note mapping to a device mapper.
    """

    def __init__(self, mapper: NoteMapper):
        """
        Initialize generic input parser.

        Args:
            mapper: Device-specific note mapper for converting
                   hardware MIDI notes to logical pad indices
        """
        self.mapper = mapper

    def parse_message(self, msg: mido.Message) -> Optional[DeviceEvent]:
        """
        Parse incoming MIDI message into device events.

        Transforms hardware MIDI note numbers to logical pad indices
        using the device-specific note mapper.

        Args:
            msg: MIDI message

        Returns:
            DeviceEvent with logical pad index, or None if message
            should be ignored or is not supported
        """
        # Filter out clock messages
        if msg.type == 'clock':
            return None

        # Handle note on/off
        if msg.type == 'note_on':
            # Convert note to logical index using device mapper
            pad_index = self.mapper.note_to_index(msg.note)
            if pad_index is None:
                return None  # Invalid note, not a grid pad

            # Note on with velocity 0 is actually note off
            if msg.velocity > 0:
                return PadPressEvent(pad_index, msg.velocity)
            else:
                return PadReleaseEvent(pad_index)

        elif msg.type == 'note_off':
            pad_index = self.mapper.note_to_index(msg.note)
            if pad_index is None:
                return None
            return PadReleaseEvent(pad_index)

        elif msg.type == 'control_change':
            return ControlChangeEvent(msg.control, msg.value)

        return None
