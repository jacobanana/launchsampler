"""Launchpad model detection and metadata."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class LaunchpadModel(Enum):
    """Launchpad hardware models."""
    X = "x"
    MINI_MK3 = "mini"
    PRO_MK3 = "pro"

    @property
    def sysex_header(self) -> list[int]:
        """Get SysEx header for this model."""
        return {
            LaunchpadModel.X: [0x00, 0x20, 0x29, 0x02, 0x0C],
            LaunchpadModel.MINI_MK3: [0x00, 0x20, 0x29, 0x02, 0x0D],
            LaunchpadModel.PRO_MK3: [0x00, 0x20, 0x29, 0x02, 0x0E],
        }[self]

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        return {
            LaunchpadModel.X: "Launchpad X",
            LaunchpadModel.MINI_MK3: "Launchpad Mini MK3",
            LaunchpadModel.PRO_MK3: "Launchpad Pro MK3",
        }[self]

    @classmethod
    def detect(cls, port_name: str) -> Optional['LaunchpadModel']:
        """
        Detect Launchpad model from MIDI port name.

        Args:
            port_name: MIDI port name string

        Returns:
            Detected LaunchpadModel or None if not recognized
        """
        port_upper = port_name.upper()

        if "MINI" in port_upper or "LPMINIMK3" in port_upper:
            return cls.MINI_MK3
        elif "PRO" in port_upper or "LPPROMK3" in port_upper:
            return cls.PRO_MK3
        elif "LPX" in port_upper or ("LAUNCHPAD" in port_upper and "X" in port_upper):
            return cls.X

        # Default to X for generic "Launchpad" ports
        if "LAUNCHPAD" in port_upper:
            return cls.X

        return None


@dataclass
class LaunchpadInfo:
    """Metadata about a Launchpad device."""
    model: LaunchpadModel
    port_name: str
    num_pads: int = 64  # 8x8 grid for all current models
    grid_size: int = 8

    @classmethod
    def from_port(cls, port_name: str) -> Optional['LaunchpadInfo']:
        """Create LaunchpadInfo by detecting model from port name."""
        model = LaunchpadModel.detect(port_name)
        if model is None:
            return None
        return cls(model=model, port_name=port_name)
