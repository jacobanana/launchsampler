"""Launchpad input parsing."""

from typing import Optional
import mido
from launchsampler.devices.protocols import DeviceInput, DeviceEvent, PadPressEvent, PadReleaseEvent, ControlChangeEvent
from .model import LaunchpadModel
from .mapper import LaunchpadNoteMapper


class LaunchpadInput(DeviceInput):
    """Parse Launchpad MIDI input into device events."""

    def __init__(self, model: LaunchpadModel):
        """
        Initialize input parser.

        Args:
            model: LaunchpadModel for note mapping
        """
        self.model = model
        self.mapper = LaunchpadNoteMapper(model)

    def parse_message(self, msg: mido.Message) -> Optional[DeviceEvent]:
        """
        Parse incoming MIDI message into Launchpad events.

        Transforms hardware MIDI note numbers to logical pad indices
        using the note mapper.

        Args:
            msg: MIDI message

        Returns:
            DeviceEvent with logical pad index, or None
        """
        # Filter out clock messages
        if msg.type == 'clock':
            return None

        # Handle note on/off
        if msg.type == 'note_on':
            # Convert note to logical index
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
