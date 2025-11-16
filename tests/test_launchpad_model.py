"""Unit tests for LaunchpadModel and LaunchpadInfo."""

import pytest
from launchsampler.devices.launchpad import LaunchpadModel, LaunchpadInfo


class TestLaunchpadModel:
    """Test Launchpad model detection and metadata."""

    def test_detect_mini_mk3(self):
        """Test detection of Mini MK3."""
        assert LaunchpadModel.detect("LPMiniMK3 MIDI 0") == LaunchpadModel.MINI_MK3
        assert LaunchpadModel.detect("MIDIIN2 (LPMiniMK3 MIDI) 1") == LaunchpadModel.MINI_MK3
        assert LaunchpadModel.detect("Launchpad Mini MK3") == LaunchpadModel.MINI_MK3

    def test_detect_pro_mk3(self):
        """Test detection of Pro MK3."""
        assert LaunchpadModel.detect("LPProMK3 MIDI 0") == LaunchpadModel.PRO_MK3
        assert LaunchpadModel.detect("Launchpad Pro MK3") == LaunchpadModel.PRO_MK3

    def test_detect_x(self):
        """Test detection of Launchpad X."""
        assert LaunchpadModel.detect("LPX MIDI 0") == LaunchpadModel.X
        assert LaunchpadModel.detect("Launchpad X") == LaunchpadModel.X

    def test_detect_generic_launchpad(self):
        """Test that generic 'Launchpad' defaults to X."""
        assert LaunchpadModel.detect("Launchpad") == LaunchpadModel.X

    def test_detect_case_insensitive(self):
        """Test that detection is case insensitive."""
        assert LaunchpadModel.detect("lpminimk3") == LaunchpadModel.MINI_MK3
        assert LaunchpadModel.detect("lppromk3") == LaunchpadModel.PRO_MK3
        assert LaunchpadModel.detect("lpx") == LaunchpadModel.X

    def test_detect_invalid(self):
        """Test that invalid port names return None."""
        assert LaunchpadModel.detect("Some Other Device") is None
        assert LaunchpadModel.detect("MIDI Keyboard") is None
        assert LaunchpadModel.detect("") is None

    def test_sysex_header_mini_mk3(self):
        """Test SysEx header for Mini MK3."""
        assert LaunchpadModel.MINI_MK3.sysex_header == [0x00, 0x20, 0x29, 0x02, 0x0D]

    def test_sysex_header_pro_mk3(self):
        """Test SysEx header for Pro MK3."""
        assert LaunchpadModel.PRO_MK3.sysex_header == [0x00, 0x20, 0x29, 0x02, 0x0E]

    def test_sysex_header_x(self):
        """Test SysEx header for Launchpad X."""
        assert LaunchpadModel.X.sysex_header == [0x00, 0x20, 0x29, 0x02, 0x0C]

    def test_display_name_mini_mk3(self):
        """Test display name for Mini MK3."""
        assert LaunchpadModel.MINI_MK3.display_name == "Launchpad Mini MK3"

    def test_display_name_pro_mk3(self):
        """Test display name for Pro MK3."""
        assert LaunchpadModel.PRO_MK3.display_name == "Launchpad Pro MK3"

    def test_display_name_x(self):
        """Test display name for Launchpad X."""
        assert LaunchpadModel.X.display_name == "Launchpad X"


class TestLaunchpadInfo:
    """Test LaunchpadInfo metadata."""

    def test_from_port_mini_mk3(self):
        """Test creating LaunchpadInfo from Mini MK3 port."""
        info = LaunchpadInfo.from_port("LPMiniMK3 MIDI 0")
        assert info is not None
        assert info.model == LaunchpadModel.MINI_MK3
        assert info.port_name == "LPMiniMK3 MIDI 0"
        assert info.num_pads == 64
        assert info.grid_size == 8

    def test_from_port_pro_mk3(self):
        """Test creating LaunchpadInfo from Pro MK3 port."""
        info = LaunchpadInfo.from_port("LPProMK3 MIDI 0")
        assert info is not None
        assert info.model == LaunchpadModel.PRO_MK3
        assert info.port_name == "LPProMK3 MIDI 0"

    def test_from_port_x(self):
        """Test creating LaunchpadInfo from Launchpad X port."""
        info = LaunchpadInfo.from_port("LPX MIDI 0")
        assert info is not None
        assert info.model == LaunchpadModel.X
        assert info.port_name == "LPX MIDI 0"

    def test_from_port_invalid(self):
        """Test that invalid ports return None."""
        assert LaunchpadInfo.from_port("Invalid Device") is None
        assert LaunchpadInfo.from_port("") is None

    def test_direct_construction(self):
        """Test direct construction of LaunchpadInfo."""
        info = LaunchpadInfo(
            model=LaunchpadModel.MINI_MK3,
            port_name="Test Port"
        )
        assert info.model == LaunchpadModel.MINI_MK3
        assert info.port_name == "Test Port"
        assert info.num_pads == 64
        assert info.grid_size == 8
