"""Unit tests for LaunchpadSysEx."""

import pytest
import mido
from launchsampler.devices.launchpad import LaunchpadModel, LaunchpadSysEx, LightingMode


class TestLaunchpadSysEx:
    """Test SysEx message building."""

    @pytest.fixture
    def sysex_mini(self):
        """Create SysEx builder for Mini MK3."""
        return LaunchpadSysEx(LaunchpadModel.MINI_MK3)

    @pytest.fixture
    def sysex_pro(self):
        """Create SysEx builder for Pro MK3."""
        return LaunchpadSysEx(LaunchpadModel.PRO_MK3)

    @pytest.fixture
    def sysex_x(self):
        """Create SysEx builder for Launchpad X."""
        return LaunchpadSysEx(LaunchpadModel.X)

    def test_programmer_mode_enable(self, sysex_mini):
        """Test enabling programmer mode."""
        msg = sysex_mini.programmer_mode(enable=True)

        assert msg.type == 'sysex'
        assert list(msg.data) == [0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01]

    def test_programmer_mode_disable(self, sysex_mini):
        """Test disabling programmer mode."""
        msg = sysex_mini.programmer_mode(enable=False)

        assert msg.type == 'sysex'
        assert list(msg.data) == [0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x00]

    def test_programmer_mode_different_models(self, sysex_mini, sysex_pro, sysex_x):
        """Test that different models use different headers."""
        msg_mini = sysex_mini.programmer_mode(enable=True)
        msg_pro = sysex_pro.programmer_mode(enable=True)
        msg_x = sysex_x.programmer_mode(enable=True)

        # Headers should differ
        assert list(msg_mini.data[:5]) == [0x00, 0x20, 0x29, 0x02, 0x0D]  # Mini
        assert list(msg_pro.data[:5]) == [0x00, 0x20, 0x29, 0x02, 0x0E]  # Pro
        assert list(msg_x.data[:5]) == [0x00, 0x20, 0x29, 0x02, 0x0C]  # X

        # Commands should be the same
        assert list(msg_mini.data[5:]) == [0x0E, 0x01]
        assert list(msg_pro.data[5:]) == [0x0E, 0x01]
        assert list(msg_x.data[5:]) == [0x0E, 0x01]

    def test_led_lighting_single_rgb(self, sysex_mini):
        """Test LED lighting with single RGB spec."""
        spec = (LightingMode.RGB.value, 11, 127, 64, 32)
        msg = sysex_mini.led_lighting([spec])

        assert msg.type == 'sysex'
        # Header + 0x03 (LED command) + spec
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 3, 11, 127, 64, 32]
        assert list(msg.data) == expected

    def test_led_lighting_single_static(self, sysex_mini):
        """Test LED lighting with static color."""
        spec = (LightingMode.STATIC.value, 11, 5)  # palette color 5
        msg = sysex_mini.led_lighting([spec])

        assert msg.type == 'sysex'
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, 0, 11, 5]
        assert list(msg.data) == expected

    def test_led_lighting_multiple_specs(self, sysex_mini):
        """Test LED lighting with multiple specs."""
        specs = [
            (LightingMode.RGB.value, 11, 127, 0, 0),  # Red
            (LightingMode.RGB.value, 12, 0, 127, 0),  # Green
            (LightingMode.RGB.value, 13, 0, 0, 127),  # Blue
        ]
        msg = sysex_mini.led_lighting(specs)

        assert msg.type == 'sysex'
        # Header + 0x03 + all specs concatenated
        expected = [
            0x00, 0x20, 0x29, 0x02, 0x0D, 0x03,  # Header + LED command
            3, 11, 127, 0, 0,  # Red
            3, 12, 0, 127, 0,  # Green
            3, 13, 0, 0, 127,  # Blue
        ]
        assert list(msg.data) == expected

    def test_led_lighting_empty_specs(self, sysex_mini):
        """Test LED lighting with no specs."""
        msg = sysex_mini.led_lighting([])

        assert msg.type == 'sysex'
        # Header + 0x03, no specs
        expected = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x03]
        assert list(msg.data) == expected

    def test_lighting_mode_values(self):
        """Test that LightingMode enum has correct values."""
        assert LightingMode.STATIC.value == 0
        assert LightingMode.FLASHING.value == 1
        assert LightingMode.PULSING.value == 2
        assert LightingMode.RGB.value == 3
