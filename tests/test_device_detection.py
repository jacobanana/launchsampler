"""Tests for device detection and registry functionality."""

import pytest
from launchsampler.devices.registry import DeviceRegistry
from launchsampler.devices.config import DeviceConfig


@pytest.fixture
def registry():
    """Create a DeviceRegistry instance for testing."""
    return DeviceRegistry()


class TestDeviceDetection:
    """Test device detection logic."""

    def test_launchpad_mini_mk3_detection(self, registry):
        """Test that Launchpad Mini MK3 is correctly detected on macOS."""
        # Real port names from macOS
        port_names = [
            "Launchpad Mini MK3 LPMiniMK3 DAW In",
            "Launchpad Mini MK3 LPMiniMK3 DAW Out",
            "Launchpad Mini MK3 LPMiniMK3 MIDI In",
            "Launchpad Mini MK3 LPMiniMK3 MIDI Out",
        ]

        for port_name in port_names:
            config = registry.detect_device(port_name)
            assert config is not None, f"Failed to detect device from: {port_name}"
            assert config.model == "Launchpad Mini MK3", (
                f"Wrong model detected for {port_name}: "
                f"expected 'Launchpad Mini MK3', got '{config.model}'"
            )

    def test_launchpad_pro_mk3_detection(self, registry):
        """Test that Launchpad Pro MK3 is correctly detected."""
        port_names = [
            "Launchpad Pro MK3 LPProMK3 MIDI 0",
            "Launchpad Pro LPProMK3 DAW",
        ]

        for port_name in port_names:
            config = registry.detect_device(port_name)
            assert config is not None, f"Failed to detect device from: {port_name}"
            assert config.model == "Launchpad Pro MK3", (
                f"Wrong model detected for {port_name}: "
                f"expected 'Launchpad Pro MK3', got '{config.model}'"
            )

    def test_launchpad_x_detection(self, registry):
        """Test that Launchpad X is correctly detected."""
        port_names = [
            "Launchpad X LPX MIDI In",
            "Launchpad X MIDI Out",
        ]

        for port_name in port_names:
            config = registry.detect_device(port_name)
            assert config is not None, f"Failed to detect device from: {port_name}"
            assert config.model == "Launchpad X", (
                f"Wrong model detected for {port_name}: "
                f"expected 'Launchpad X', got '{config.model}'"
            )

    def test_no_match_for_unknown_device(self, registry):
        """Test that unknown devices return None."""
        port_names = [
            "Random MIDI Device",
            "Unknown Controller",
            "Generic USB MIDI",
        ]

        for port_name in port_names:
            config = registry.detect_device(port_name)
            assert config is None, (
                f"Should not detect device from: {port_name}, "
                f"but got: {config.model if config else None}"
            )

    def test_pattern_specificity_mini_vs_pro(self, registry):
        """
        Test that specific patterns take precedence over generic ones.

        This is a regression test for the bug where Launchpad Mini MK3
        was detected as Launchpad Pro MK3 on macOS.
        """
        # Port name contains both "Launchpad" and "Mini"
        port_name = "Launchpad Mini MK3 LPMiniMK3 MIDI In"

        config = registry.detect_device(port_name)
        assert config is not None
        assert config.model == "Launchpad Mini MK3", (
            "Launchpad Mini MK3 should be detected correctly, "
            f"not as {config.model}"
        )

        # Verify it has the correct SysEx header for Mini (not Pro)
        assert config.sysex_header == [0, 32, 41, 2, 13], (
            f"Wrong SysEx header: {config.sysex_header}. "
            "Should be [0, 32, 41, 2, 13] for Mini MK3"
        )


class TestDeviceConfig:
    """Test DeviceConfig functionality."""

    def test_device_config_matches(self, registry):
        """Test that DeviceConfig.matches() works correctly."""
        # Get the Mini MK3 config
        mini_config = None
        for config in registry.devices:
            if config.model == "Launchpad Mini MK3":
                mini_config = config
                break

        assert mini_config is not None, "Could not find Launchpad Mini MK3 config"

        # Should match Mini-specific patterns
        assert mini_config.matches("Launchpad Mini MK3 MIDI")
        assert mini_config.matches("LPMiniMK3 DAW Out")

        # Should not match Pro-specific patterns
        assert not mini_config.matches("Launchpad Pro MK3 MIDI")
        assert not mini_config.matches("LPProMK3 DAW")

    def test_all_devices_have_unique_models(self, registry):
        """Test that all device models are unique."""
        models = [config.model for config in registry.devices]
        assert len(models) == len(set(models)), (
            f"Duplicate device models found: {models}"
        )

    def test_all_devices_have_detection_patterns(self, registry):
        """Test that all devices have at least one detection pattern."""
        for config in registry.devices:
            assert len(config.detection_patterns) > 0, (
                f"Device {config.model} has no detection patterns"
            )
