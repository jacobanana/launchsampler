"""Unit tests for LaunchpadInput."""

import pytest
import mido
from launchsampler.devices.launchpad import LaunchpadModel, LaunchpadInput
from launchsampler.devices.protocols import PadPressEvent, PadReleaseEvent


class TestLaunchpadInput:
    """Test Launchpad input message parsing."""

    @pytest.fixture
    def input_parser(self):
        """Create a LaunchpadInput for testing."""
        return LaunchpadInput(LaunchpadModel.MINI_MK3)

    def test_parse_note_on_press(self, input_parser):
        """Test parsing note_on with velocity > 0 as pad press."""
        msg = mido.Message('note_on', note=11, velocity=100)
        event = input_parser.parse_message(msg)

        assert isinstance(event, PadPressEvent)
        assert event.pad_index == 0  # Note 11 → index 0
        assert event.velocity == 100

    def test_parse_note_on_release(self, input_parser):
        """Test parsing note_on with velocity 0 as pad release."""
        msg = mido.Message('note_on', note=11, velocity=0)
        event = input_parser.parse_message(msg)

        assert isinstance(event, PadReleaseEvent)
        assert event.pad_index == 0

    def test_parse_note_off(self, input_parser):
        """Test parsing note_off as pad release."""
        msg = mido.Message('note_off', note=11, velocity=0)
        event = input_parser.parse_message(msg)

        assert isinstance(event, PadReleaseEvent)
        assert event.pad_index == 0

    def test_parse_different_notes(self, input_parser):
        """Test parsing different notes."""
        # Bottom-left (note 11 → index 0)
        msg = mido.Message('note_on', note=11, velocity=100)
        event = input_parser.parse_message(msg)
        assert event.pad_index == 0

        # Bottom-right (note 18 → index 7)
        msg = mido.Message('note_on', note=18, velocity=100)
        event = input_parser.parse_message(msg)
        assert event.pad_index == 7

        # Top-left (note 81 → index 56)
        msg = mido.Message('note_on', note=81, velocity=100)
        event = input_parser.parse_message(msg)
        assert event.pad_index == 56

        # Top-right (note 88 → index 63)
        msg = mido.Message('note_on', note=88, velocity=100)
        event = input_parser.parse_message(msg)
        assert event.pad_index == 63

    def test_parse_invalid_note(self, input_parser):
        """Test that invalid notes return None."""
        # Note outside valid range
        msg = mido.Message('note_on', note=0, velocity=100)
        assert input_parser.parse_message(msg) is None

        msg = mido.Message('note_on', note=10, velocity=100)
        assert input_parser.parse_message(msg) is None

        msg = mido.Message('note_on', note=89, velocity=100)
        assert input_parser.parse_message(msg) is None

        # Invalid column (note 19 = row 0, col 8)
        msg = mido.Message('note_on', note=19, velocity=100)
        assert input_parser.parse_message(msg) is None

    def test_parse_clock_message(self, input_parser):
        """Test that clock messages are filtered out."""
        msg = mido.Message('clock')
        assert input_parser.parse_message(msg) is None

    def test_parse_other_message_types(self, input_parser):
        """Test control_change returns ControlChangeEvent, other types return None."""
        from launchsampler.devices.protocols import ControlChangeEvent

        # Control change should return ControlChangeEvent
        msg = mido.Message('control_change', control=7, value=100)
        event = input_parser.parse_message(msg)
        assert isinstance(event, ControlChangeEvent)
        assert event.control == 7
        assert event.value == 100

        # Other message types should still return None
        msg = mido.Message('program_change', program=0)
        assert input_parser.parse_message(msg) is None

    def test_velocity_values(self, input_parser):
        """Test different velocity values."""
        msg = mido.Message('note_on', note=11, velocity=1)
        event = input_parser.parse_message(msg)
        assert event.velocity == 1

        msg = mido.Message('note_on', note=11, velocity=64)
        event = input_parser.parse_message(msg)
        assert event.velocity == 64

        msg = mido.Message('note_on', note=11, velocity=127)
        event = input_parser.parse_message(msg)
        assert event.velocity == 127
