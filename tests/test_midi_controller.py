"""Tests for MIDI controller."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from launchsampler.devices import DeviceController
from launchsampler.models import Color


@pytest.mark.unit
class TestDeviceController:
    """Test DeviceController class (formerly DeviceController)."""

    def test_observer_registration(self):
        """Test observer registration."""
        from launchsampler.protocols import MidiObserver, MidiEvent

        controller = DeviceController()
        observer = Mock(spec=MidiObserver)

        controller.register_observer(observer)
        assert observer in controller._observers

        controller.unregister_observer(observer)
        assert observer not in controller._observers

    @patch('launchsampler.midi.input_manager.mido.get_input_names')
    @patch('launchsampler.midi.output_manager.mido.get_output_names')
    def test_start_stop(self, mock_get_output, mock_get_input):
        """Test starting and stopping controller."""
        mock_get_input.return_value = []
        mock_get_output.return_value = []

        controller = DeviceController(poll_interval=0.1)

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

        with DeviceController(poll_interval=0.1) as controller:
            time.sleep(0.05)
            assert controller._midi._input_manager._running
            assert controller._midi._output_manager._running

        assert not controller._midi._input_manager._running
        assert not controller._midi._output_manager._running

    def test_set_leds_bulk_without_device(self):
        """Test set_leds_bulk returns False when no device connected."""
        controller = DeviceController()
        updates = [(0, Color(r=127, g=0, b=0)), (5, Color(r=0, g=127, b=0))]

        # Should return False when no device
        result = controller.set_leds_bulk(updates)
        assert result is False

    def test_set_leds_bulk_with_device(self):
        """Test set_leds_bulk delegates to device output."""
        controller = DeviceController()

        # Mock device and output
        mock_device = Mock()
        mock_output = Mock()
        mock_device.output = mock_output
        controller._device = mock_device

        updates = [(0, Color(r=127, g=0, b=0)), (5, Color(r=0, g=127, b=0)), (10, Color(r=0, g=0, b=127))]

        # Should delegate to device output
        result = controller.set_leds_bulk(updates)
        assert result is True
        mock_output.set_leds_bulk.assert_called_once_with(updates)

    def test_set_leds_bulk_handles_errors(self):
        """Test set_leds_bulk returns False on error."""
        controller = DeviceController()

        # Mock device that raises exception
        mock_device = Mock()
        mock_output = Mock()
        mock_output.set_leds_bulk.side_effect = Exception("Test error")
        mock_device.output = mock_output
        controller._device = mock_device

        updates = [(0, Color(r=127, g=0, b=0))]

        # Should catch exception and return False
        result = controller.set_leds_bulk(updates)
        assert result is False
