"""Tests for MIDI controller."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from launchsampler.devices.launchpad import LaunchpadController, LaunchpadDevice
from launchsampler.models import Color


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

    def test_select_input_port_pro_mk3_windows(self):
        """Test input port selection for Launchpad Pro MK3 on Windows."""
        # Pro MK3 uses MIDI 0 for note messages (not MIDI 1!)
        ports = ["LPProMK3 MIDI 0", "MIDIIN2 (LPProMK3 MIDI) 1", "MIDIIN3 (LPProMK3 MIDI) 2"]
        assert LaunchpadDevice.select_input_port(ports) == "LPProMK3 MIDI 0"

        # If MIDI 0 is not available, fall back to MIDI 1
        ports = ["LPProMK3 MIDI 1", "LPProMK3 MIDI 2"]
        assert LaunchpadDevice.select_input_port(ports) == "LPProMK3 MIDI 1"

        # Standard naming convention
        ports = ["LPProMK3 MIDI 0", "LPProMK3 MIDI 1", "LPProMK3 MIDI 2"]
        assert LaunchpadDevice.select_input_port(ports) == "LPProMK3 MIDI 0"

    def test_select_input_port_mini_mk3_windows(self):
        """Test input port selection for Launchpad Mini MK3 on Windows."""
        # Mini MK3 uses MIDIIN2 pattern for note messages
        ports = [
            "LPMiniMK3 MIDI 0",
            "MIDIIN2 (LPMiniMK3 MIDI) 1",
            "MIDIIN3 (LPMiniMK3 MIDI) 2"
        ]
        assert LaunchpadDevice.select_input_port(ports) == "MIDIIN2 (LPMiniMK3 MIDI) 1"

        # If MIDIIN2 is not available, fall back to MIDI 1
        ports = ["LPMiniMK3 MIDI 0", "LPMiniMK3 MIDI 1"]
        assert LaunchpadDevice.select_input_port(ports) == "LPMiniMK3 MIDI 1"

        # If only MIDI 0 available, use it
        ports = ["LPMiniMK3 MIDI 0"]
        assert LaunchpadDevice.select_input_port(ports) == "LPMiniMK3 MIDI 0"

    def test_select_input_port_mini_mk3_macos(self):
        """Test input port selection for Launchpad Mini MK3 on macOS."""
        # macOS: prefer "MIDI Out" over "DAW Out" for input
        ports = [
            "Launchpad Mini MK3 LPMiniMK3 DAW Out",
            "Launchpad Mini MK3 LPMiniMK3 MIDI Out"
        ]
        assert LaunchpadDevice.select_input_port(ports) == "Launchpad Mini MK3 LPMiniMK3 MIDI Out"

        # Only DAW Out available (should skip)
        ports = ["Launchpad Mini MK3 LPMiniMK3 DAW Out"]
        assert LaunchpadDevice.select_input_port(ports) == "Launchpad Mini MK3 LPMiniMK3 DAW Out"

    def test_select_output_port_mini_mk3_macos(self):
        """Test output port selection for Launchpad Mini MK3 on macOS."""
        # macOS: prefer "MIDI In" over "DAW In" for output
        ports = [
            "Launchpad Mini MK3 LPMiniMK3 DAW In",
            "Launchpad Mini MK3 LPMiniMK3 MIDI In"
        ]
        assert LaunchpadDevice.select_output_port(ports) == "Launchpad Mini MK3 LPMiniMK3 MIDI In"

        # Only DAW In available (should skip)
        ports = ["Launchpad Mini MK3 LPMiniMK3 DAW In"]
        assert LaunchpadDevice.select_output_port(ports) == "Launchpad Mini MK3 LPMiniMK3 DAW In"

    def test_select_input_port_other_models_macos(self):
        """Test input port selection for other Launchpad models on macOS."""
        # Other models should prefer "MIDI Out" on macOS
        ports = ["Launchpad X MIDI Out", "Launchpad X DAW Out"]
        assert LaunchpadDevice.select_input_port(ports) == "Launchpad X MIDI Out"

    def test_select_input_port_other_models_windows(self):
        """Test input port selection for other Launchpad models on Windows."""
        # Other models should prefer MIDI 1 on Windows
        ports = ["Launchpad X MIDI 0", "Launchpad X MIDI 1", "Launchpad X MIDI 2"]
        assert LaunchpadDevice.select_input_port(ports) == "Launchpad X MIDI 1"

        # Without MIDI 1, takes first
        ports = ["LPX MIDI 0", "LPX MIDI 2"]
        assert LaunchpadDevice.select_input_port(ports) == "LPX MIDI 0"

        # Empty list
        assert LaunchpadDevice.select_input_port([]) is None


@pytest.mark.unit
class TestLaunchpadController:
    """Test LaunchpadController class."""

    def test_observer_registration(self):
        """Test observer registration."""
        from launchsampler.protocols import MidiObserver, MidiEvent

        controller = LaunchpadController()
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

    def test_set_leds_bulk_without_device(self):
        """Test set_leds_bulk returns False when no device connected."""
        controller = LaunchpadController()
        updates = [(0, Color(r=127, g=0, b=0)), (5, Color(r=0, g=127, b=0))]

        # Should return False when no device
        result = controller.set_leds_bulk(updates)
        assert result is False

    def test_set_leds_bulk_with_device(self):
        """Test set_leds_bulk delegates to device output."""
        controller = LaunchpadController()

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
        controller = LaunchpadController()

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
