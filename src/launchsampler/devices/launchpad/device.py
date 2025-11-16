"""Launchpad device implementation."""

import logging
from typing import Optional
from launchsampler.midi import MidiManager
from launchsampler.devices.protocols import Device, DeviceInput, DeviceOutput
from .model import LaunchpadInfo, LaunchpadModel
from .input import LaunchpadInput
from .output import LaunchpadOutput
from .mapper import LaunchpadNoteMapper

logger = logging.getLogger(__name__)


class LaunchpadDevice(Device):
    """
    Complete Launchpad device with input and output.

    Provides unified interface hiding hardware-specific note mapping.
    Application code works with logical pad indices (0-63) only.
    """

    # Device name patterns for detection
    PATTERNS = [
        "Launchpad X",
        "Launchpad Mini",
        "Launchpad Pro",
        "LPProMK3",
        "LPMiniMK3",
        "LPX",
        "Launchpad",
    ]

    # Launchpad hardware constants
    NUM_PADS = 64  # 8x8 grid
    GRID_SIZE = 8  # 8x8 grid

    def __init__(self, midi_manager: MidiManager, port_name: str):
        """
        Initialize Launchpad device.

        Args:
            midi_manager: MIDI manager instance
            port_name: MIDI port name for this device

        Raises:
            ValueError: If port_name doesn't match a recognized Launchpad
        """
        self.info = LaunchpadInfo.from_port(port_name)
        if self.info is None:
            raise ValueError(f"Port '{port_name}' is not a recognized Launchpad")

        self._input = LaunchpadInput(self.info.model)
        self._output = LaunchpadOutput(midi_manager, self.info)

    @property
    def input(self) -> DeviceInput:
        """Get input handler."""
        return self._input

    @property
    def output(self) -> DeviceOutput:
        """Get output controller."""
        return self._output

    @staticmethod
    def matches(port_name: str) -> bool:
        """Check if port name matches a Launchpad device."""
        return any(pattern in port_name for pattern in LaunchpadDevice.PATTERNS)

    @staticmethod
    def select_port(matching_ports: list[str]) -> Optional[str]:
        """
        Select the best port from matching Launchpad ports.

        TODO: implement a more robust selection strategy that works on any system.

        Launchpad devices often have multiple MIDI ports with different naming conventions:
        - Launchpad Pro MK3: Note messages on "LPProMK3 MIDI 0" (uses port 0, not port 1!)
        - Launchpad Mini MK3: Note messages on "MIDIIN2 (LPMiniMK3 MIDI) 1" (uses MIDIIN2)

        For note input/output, we need to select the correct port based on the model.

        Args:
            matching_ports: List of port names that match Launchpad patterns

        Returns:
            Selected port name, or None if list is empty
        """
        if not matching_ports:
            return None

        # Check if this is a Mini MK3 (uses MIDIIN2/MIDIIN3 pattern for note messages)
        if any("LPMiniMK3" in p for p in matching_ports):
            # For Mini MK3, prefer MIDIIN2 (LPMiniMK3 MIDI) which carries note messages
            midiin2_ports = [p for p in matching_ports if "MIDIIN2" in p and "LPMiniMK3" in p]
            if midiin2_ports:
                return midiin2_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # Check if this is a Pro MK3 (uses MIDI 0 for note messages, not MIDI 1!)
        if any("LPProMK3" in p for p in matching_ports):
            # For Pro MK3, prefer "LPProMK3 MIDI 0" which carries note messages
            midi0_ports = [p for p in matching_ports if "LPProMK3 MIDI 0" in p]
            if midi0_ports:
                return midi0_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # For other Launchpad models (X, etc.), prefer "MIDI 1"
        midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
        if midi1_ports:
            return midi1_ports[0]

        # Fall back to first match
        return matching_ports[0]

