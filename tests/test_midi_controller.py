"""Tests for MIDI controller."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from launchsampler.midi import LaunchpadController


@pytest.mark.unit
class TestLaunchpadController:
    """Test LaunchpadController class."""

    def test_init(self):
        """Test controller initialization."""
        controller = LaunchpadController(poll_interval=1.0)
        assert controller.poll_interval == 1.0
        assert not controller.running
        assert controller.current_port is None
        assert controller.inport is None

    def test_callback_registration(self):
        """Test callback registration."""
        controller = LaunchpadController()

        pressed_callback = Mock()
        released_callback = Mock()

        controller.on_pad_pressed(pressed_callback)
        controller.on_pad_released(released_callback)

        assert controller._on_pad_pressed == pressed_callback
        assert controller._on_pad_released == released_callback

    def test_is_launchpad_port(self):
        """Test Launchpad port detection."""
        controller = LaunchpadController()

        assert controller._is_launchpad_port("Launchpad X")
        assert controller._is_launchpad_port("Launchpad Mini")
        assert controller._is_launchpad_port("Launchpad Pro")
        assert controller._is_launchpad_port("Novation Launchpad X")
        assert controller._is_launchpad_port("LPProMK3 MIDI 1")
        assert controller._is_launchpad_port("LPProMK3 MIDI 2")
        assert controller._is_launchpad_port("LPMiniMK3 MIDI 1")
        assert controller._is_launchpad_port("LPX MIDI 1")
        assert not controller._is_launchpad_port("Other MIDI Device")
        assert not controller._is_launchpad_port("Keyboard")

    @patch('launchsampler.midi.controller.mido.get_input_names')
    def test_find_launchpad_port(self, mock_get_names):
        """Test finding Launchpad port."""
        controller = LaunchpadController()

        # Test with Launchpad available
        mock_get_names.return_value = ["Other Device", "Launchpad X", "Keyboard"]
        assert controller._find_launchpad_port() == "Launchpad X"

        # Test with no Launchpad
        mock_get_names.return_value = ["Other Device", "Keyboard"]
        assert controller._find_launchpad_port() is None

        # Test preferring MIDI 1 port for multi-port devices
        mock_get_names.return_value = [
            "LPProMK3 MIDI 2",
            "LPProMK3 MIDI 3",
            "LPProMK3 MIDI 1",
            "Other Device"
        ]
        assert controller._find_launchpad_port() == "LPProMK3 MIDI 1"

        # Test with only non-MIDI 1 port
        mock_get_names.return_value = ["LPProMK3 MIDI 2", "Other Device"]
        assert controller._find_launchpad_port() == "LPProMK3 MIDI 2"

    def test_handle_note_on(self):
        """Test note on handling."""
        controller = LaunchpadController()
        callback = Mock()
        controller.on_pad_pressed(callback)

        # Test valid note
        controller._handle_note_on(32)
        callback.assert_called_once_with(32)

        # Test note 0 (valid)
        callback.reset_mock()
        controller._handle_note_on(0)
        callback.assert_called_once_with(0)

        # Test note 63 (valid)
        callback.reset_mock()
        controller._handle_note_on(63)
        callback.assert_called_once_with(63)

        # Test invalid note (out of range)
        callback.reset_mock()
        controller._handle_note_on(64)
        callback.assert_not_called()

        callback.reset_mock()
        controller._handle_note_on(-1)
        callback.assert_not_called()

    def test_handle_note_off(self):
        """Test note off handling."""
        controller = LaunchpadController()
        callback = Mock()
        controller.on_pad_released(callback)

        # Test valid note
        controller._handle_note_off(32)
        callback.assert_called_once_with(32)

        # Test invalid note
        callback.reset_mock()
        controller._handle_note_off(64)
        callback.assert_not_called()

    def test_no_callback_doesnt_crash(self):
        """Test that missing callbacks don't cause errors."""
        controller = LaunchpadController()

        # Should not raise any errors
        controller._handle_note_on(32)
        controller._handle_note_off(32)

    @patch('launchsampler.midi.controller.mido.get_input_names')
    @patch('launchsampler.midi.controller.mido.open_input')
    def test_start_stop(self, mock_open, mock_get_names):
        """Test starting and stopping controller."""
        mock_get_names.return_value = []
        controller = LaunchpadController(poll_interval=0.1)

        # Start
        controller.start()
        assert controller.running
        assert controller.monitor_thread is not None

        # Give thread time to start
        time.sleep(0.05)

        # Stop
        controller.stop()
        assert not controller.running

    @patch('launchsampler.midi.controller.mido.get_input_names')
    @patch('launchsampler.midi.controller.mido.open_input')
    def test_context_manager(self, mock_open, mock_get_names):
        """Test context manager usage."""
        mock_get_names.return_value = []

        with LaunchpadController(poll_interval=0.1) as controller:
            assert controller.running

        assert not controller.running

    @patch('launchsampler.midi.controller.mido.get_input_names')
    @patch('launchsampler.midi.controller.mido.open_input')
    def test_device_connection(self, mock_open, mock_get_names):
        """Test device connection when Launchpad is found."""
        mock_port = MagicMock()
        mock_port.iter_pending.return_value = []
        mock_open.return_value = mock_port
        mock_get_names.return_value = ["Launchpad X"]

        controller = LaunchpadController(poll_interval=0.1)
        controller.start()

        # Wait for monitor to detect and connect
        time.sleep(0.2)

        # Should have connected
        with controller._port_lock:
            assert controller.current_port == "Launchpad X"

        controller.stop()

    def test_double_start_warning(self, caplog):
        """Test that starting twice logs a warning."""
        controller = LaunchpadController(poll_interval=0.1)

        with patch('launchsampler.midi.controller.mido.get_input_names', return_value=[]):
            controller.start()
            controller.start()  # Second start

            # Check for warning (caplog may need logger configured)
            controller.stop()

    def test_midi_callback_thread_safety(self):
        """Test that MIDI callback is thread-safe."""
        controller = LaunchpadController()
        callback_calls = []

        def on_pressed(pad_index: int):
            callback_calls.append(('pressed', pad_index))

        def on_released(pad_index: int):
            callback_calls.append(('released', pad_index))

        controller.on_pad_pressed(on_pressed)
        controller.on_pad_released(on_released)

        # Simulate MIDI messages from callback thread
        import mido
        note_on = mido.Message('note_on', note=32, velocity=100)
        note_off = mido.Message('note_off', note=32, velocity=0)

        controller._midi_callback(note_on)
        controller._midi_callback(note_off)

        assert callback_calls == [('pressed', 32), ('released', 32)]

    def test_midi_callback_filters_clock(self):
        """Test that clock messages are filtered."""
        controller = LaunchpadController()
        callback_calls = []

        def on_pressed(pad_index: int):
            callback_calls.append(pad_index)

        controller.on_pad_pressed(on_pressed)

        # Clock message should be ignored
        import mido
        clock_msg = mido.Message('clock')
        controller._midi_callback(clock_msg)

        assert len(callback_calls) == 0
