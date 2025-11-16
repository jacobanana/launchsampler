"""Unit tests for LaunchpadOutput."""

import pytest
from unittest.mock import Mock, MagicMock
from launchsampler.devices.launchpad import LaunchpadOutput, LaunchpadModel, LaunchpadInfo, LightingMode
from launchsampler.models import Color


class TestLaunchpadOutput:
    """Test Launchpad output/LED control."""

    @pytest.fixture
    def mock_midi_manager(self):
        """Create mock MIDI manager."""
        mock = Mock()
        mock.send = Mock(return_value=True)
        return mock

    @pytest.fixture
    def launchpad_info(self):
        """Create Launchpad info for Mini MK3."""
        return LaunchpadInfo(
            model=LaunchpadModel.MINI_MK3,
            port_name="MIDIIN2 (LPMiniMK3 MIDI) 1"
        )

    @pytest.fixture
    def output(self, mock_midi_manager, launchpad_info):
        """Create LaunchpadOutput instance."""
        return LaunchpadOutput(mock_midi_manager, launchpad_info)

    def test_initialization(self, output, mock_midi_manager):
        """Test output initialization enters programmer mode."""
        output.initialize()

        # Should send programmer mode enable message
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'
        # Mini MK3 header + programmer mode enable
        assert list(msg.data) == [0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01]

    def test_shutdown(self, output, mock_midi_manager):
        """Test output shutdown exits programmer mode."""
        output.initialize()
        mock_midi_manager.send.reset_mock()

        output.shutdown()

        # Should send clear all, then programmer mode disable
        calls = mock_midi_manager.send.call_args_list
        assert len(calls) == 2

        # Last call should be programmer mode disable
        msg = calls[-1][0][0]
        assert msg.type == 'sysex'
        assert list(msg.data) == [0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x00]

    def test_set_led_rgb(self, output, mock_midi_manager):
        """Test setting LED with RGB color."""
        color = Color(r=127, g=64, b=32)
        output.set_led(0, color)

        # Should send RGB lighting message
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Header + LED command + RGB spec (mode=3, note=11, r=127, g=64, b=32)
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 3, 11, 127, 64, 32]
        assert list(msg.data) == expected

    def test_set_led_flashing(self, output, mock_midi_manager):
        """Test setting LED to flashing mode."""
        output.set_led_flashing(0, 5)

        # Should send flashing lighting message
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Header + LED command + flashing spec (mode=1, note=11, color_b=0, color_a=5)
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 1, 11, 0, 5]
        assert list(msg.data) == expected

    def test_set_led_pulsing(self, output, mock_midi_manager):
        """Test setting LED to pulsing mode."""
        output.set_led_pulsing(0, 10)

        # Should send pulsing lighting message
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Header + LED command + pulsing spec (mode=2, note=11, color=10)
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 2, 11, 10]
        assert list(msg.data) == expected

    def test_set_led_static(self, output, mock_midi_manager):
        """Test setting LED to static palette color."""
        output.set_led_static(0, 15)

        # Should send static lighting message
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Header + LED command + static spec (mode=0, note=11, color=15)
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 0, 11, 15]
        assert list(msg.data) == expected

    def test_set_led_different_pads(self, output, mock_midi_manager):
        """Test setting different pad indices."""
        color = Color(r=127, g=0, b=0)

        # Pad 0 (bottom-left) → note 11
        output.set_led(0, color)
        msg = mock_midi_manager.send.call_args[0][0]
        assert list(msg.data)[6:] == [3, 11, 127, 0, 0]

        # Pad 7 (bottom-right) → note 18
        output.set_led(7, color)
        msg = mock_midi_manager.send.call_args[0][0]
        assert list(msg.data)[6:] == [3, 18, 127, 0, 0]

        # Pad 63 (top-right) → note 88
        output.set_led(63, color)
        msg = mock_midi_manager.send.call_args[0][0]
        assert list(msg.data)[6:] == [3, 88, 127, 0, 0]

    def test_set_leds_bulk(self, output, mock_midi_manager):
        """Test bulk LED update."""
        updates = [
            (0, Color(r=127, g=0, b=0)),    # Red
            (1, Color(r=0, g=127, b=0)),    # Green
            (2, Color(r=0, g=0, b=127)),    # Blue
        ]

        output.set_leds_bulk(updates)

        # Should send single message with all specs
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Header + LED command + all three RGB specs
        expected = [
            0x00, 0x20, 0x29, 0x02, 0x0D, 0x03,  # Header + LED command
            3, 11, 127, 0, 0,   # Pad 0 (note 11) - Red
            3, 12, 0, 127, 0,   # Pad 1 (note 12) - Green
            3, 13, 0, 0, 127,   # Pad 2 (note 13) - Blue
        ]
        assert list(msg.data) == expected

    def test_clear_all(self, output, mock_midi_manager):
        """Test clearing all LEDs."""
        output.clear_all()

        # Should send message setting all pads to black (static mode, color 0)
        assert mock_midi_manager.send.called
        msg = mock_midi_manager.send.call_args[0][0]
        assert msg.type == 'sysex'

        # Should have header + LED command + 64 static specs
        data = list(msg.data)
        assert data[:6] == [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03]

        # Count the specs (each is 3 bytes: mode=0, note, color=0)
        specs = data[6:]
        assert len(specs) == 64 * 3  # 64 pads × 3 bytes per spec

    def test_invalid_pad_index(self, output, mock_midi_manager):
        """Test that invalid pad indices are handled gracefully."""
        color = Color(r=127, g=0, b=0)

        # Index out of range
        output.set_led(64, color)
        output.set_led(-1, color)

        # Should not crash, but shouldn't send messages either
        # (mapper returns None for invalid indices)
        assert not mock_midi_manager.send.called

    def test_midi_send_failure(self, output, mock_midi_manager):
        """Test handling of MIDI send failures."""
        mock_midi_manager.send.return_value = False

        color = Color(r=127, g=0, b=0)
        output.set_led(0, color)

        # Should not crash even if send fails
        assert mock_midi_manager.send.called
