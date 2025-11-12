"""Tests for MIDI controller."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from launchsampler.launchpad import LaunchpadController, LaunchpadDevice


@pytest.mark.unit
class TestLaunchpadDevice:
    """Test LaunchpadDevice protocol."""

    def test_matches(self):
        """Test Launchpad port detection."""
        assert LaunchpadDevice.matches("Launchpad X")
        assert LaunchpadDevice.matches("Launchpad Mini")
        assert LaunchpadDevice.matches("Launchpad Pro")
        assert LaunchpadDevice.matches("Novation Launchpad X")
        assert LaunchpadDevice.matches("LPProMK3 MIDI 1")
        assert LaunchpadDevice.matches("LPProMK3 MIDI 2")
        assert LaunchpadDevice.matches("LPMiniMK3 MIDI 1")
        assert LaunchpadDevice.matches("LPX MIDI 1")
        assert not LaunchpadDevice.matches("Other MIDI Device")
        assert not LaunchpadDevice.matches("Keyboard")

    def test_parse_input_note_on(self):
        """Test parsing note on messages."""
        import mido

        # Valid pad press
        msg = mido.Message('note_on', note=32, velocity=100)
        assert LaunchpadDevice.parse_input(msg) == ("pad_press", 32)

        # Note 0 (valid)
        msg = mido.Message('note_on', note=0, velocity=100)
        assert LaunchpadDevice.parse_input(msg) == ("pad_press", 0)

        # Note 63 (valid)
        msg = mido.Message('note_on', note=63, velocity=100)
        assert LaunchpadDevice.parse_input(msg) == ("pad_press", 63)

        # Note on with velocity 0 = note off
        msg = mido.Message('note_on', note=32, velocity=0)
        assert LaunchpadDevice.parse_input(msg) == ("pad_release", 32)

        # Out of range notes
        msg = mido.Message('note_on', note=64, velocity=100)
        assert LaunchpadDevice.parse_input(msg) is None

    def test_parse_input_note_off(self):
        """Test parsing note off messages."""
        import mido

        msg = mido.Message('note_off', note=32, velocity=0)
        assert LaunchpadDevice.parse_input(msg) == ("pad_release", 32)

        # Out of range
        msg = mido.Message('note_off', note=64, velocity=0)
        assert LaunchpadDevice.parse_input(msg) is None

    def test_parse_input_clock(self):
        """Test that clock messages are filtered."""
        import mido

        msg = mido.Message('clock')
        assert LaunchpadDevice.parse_input(msg) is None

    def test_select_port_prefers_midi1(self):
        """Test port selection prefers MIDI 1 ports."""
        ports = ["LPProMK3 MIDI 0", "LPProMK3 MIDI 2", "LPProMK3 MIDI 1"]
        assert LaunchpadDevice.select_port(ports) == "LPProMK3 MIDI 1"

        # Without MIDI 1, takes first
        ports = ["LPProMK3 MIDI 0", "LPProMK3 MIDI 2"]
        assert LaunchpadDevice.select_port(ports) == "LPProMK3 MIDI 0"

        # Empty list
        assert LaunchpadDevice.select_port([]) is None


@pytest.mark.unit
class TestLaunchpadController:
    """Test LaunchpadController class."""

    def test_callback_registration(self):
        """Test callback registration."""
        controller = LaunchpadController()

        pressed_callback = Mock()
        released_callback = Mock()

        controller.on_pad_pressed(pressed_callback)
        controller.on_pad_released(released_callback)

        assert controller._on_pad_pressed == pressed_callback
        assert controller._on_pad_released == released_callback

    def test_no_callback_doesnt_crash(self):
        """Test that missing callbacks don't cause errors."""
        controller = LaunchpadController()

        # Should not raise any errors - simulate messages
        import mido
        note_on = mido.Message('note_on', note=32, velocity=100)
        note_off = mido.Message('note_off', note=32, velocity=0)

        controller._handle_message(note_on)
        controller._handle_message(note_off)

    @patch('launchsampler.midi.input_manager.mido.get_input_names')
    @patch('launchsampler.midi.output_manager.mido.get_output_names')
    def test_start_stop(self, mock_get_output, mock_get_input):
        """Test starting and stopping controller."""
        mock_get_input.return_value = []
        mock_get_output.return_value = []

        controller = LaunchpadController(poll_interval=0.1)

        # Start
        controller.start()
        # Give thread time to start
        time.sleep(0.05)

        # Stop
        controller.stop()

    @patch('launchsampler.midi.input_manager.mido.get_input_names')
    @patch('launchsampler.midi.output_manager.mido.get_output_names')
    def test_context_manager(self, mock_get_output, mock_get_input):
        """Test context manager usage."""
        mock_get_input.return_value = []
        mock_get_output.return_value = []

        with LaunchpadController(poll_interval=0.1) as controller:
            time.sleep(0.05)
            assert controller._midi._input_manager._running
            assert controller._midi._output_manager._running

        assert not controller._midi._input_manager._running
        assert not controller._midi._output_manager._running

    def test_message_handling(self):
        """Test that MIDI messages are properly dispatched."""
        controller = LaunchpadController()
        callback_calls = []

        def on_pressed(pad_index: int):
            callback_calls.append(('pressed', pad_index))

        def on_released(pad_index: int):
            callback_calls.append(('released', pad_index))

        controller.on_pad_pressed(on_pressed)
        controller.on_pad_released(on_released)

        # Simulate MIDI messages
        import mido
        note_on = mido.Message('note_on', note=32, velocity=100)
        note_off = mido.Message('note_off', note=32, velocity=0)

        controller._handle_message(note_on)
        controller._handle_message(note_off)

        assert callback_calls == [('pressed', 32), ('released', 32)]

    def test_message_handling_filters_clock(self):
        """Test that clock messages are filtered."""
        controller = LaunchpadController()
        callback_calls = []

        def on_pressed(pad_index: int):
            callback_calls.append(pad_index)

        controller.on_pad_pressed(on_pressed)

        # Clock message should be ignored
        import mido
        clock_msg = mido.Message('clock')
        controller._handle_message(clock_msg)

        assert len(callback_calls) == 0
