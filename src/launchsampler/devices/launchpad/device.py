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
    def select_input_port(matching_ports: list[str]) -> Optional[str]:
        """
        Select the best input port from matching Launchpad ports.

        Launchpad devices have multiple MIDI ports with different naming conventions:

        Windows:
        - Launchpad Pro MK3: Note messages on "LPProMK3 MIDI 0" (uses port 0, not port 1!)
        - Launchpad Mini MK3: Note messages on "MIDIIN2 (LPMiniMK3 MIDI) 1" (uses MIDIIN2)

        macOS:
        - Launchpad Mini MK3: "Launchpad Mini MK3 LPMiniMK3 MIDI Out" for input (not DAW Out)
        - Note: On macOS, input ports end with "Out" (they output TO the computer)

        Args:
            matching_ports: List of port names that match Launchpad patterns

        Returns:
            Selected port name, or None if list is empty
        """
        if not matching_ports:
            return None

        # Check if this is a Mini MK3
        if any("LPMiniMK3" in p for p in matching_ports):
            # macOS: prefer ports ending in "MIDI Out" (not "DAW Out")
            midi_out_ports = [p for p in matching_ports if "MIDI Out" in p and "DAW" not in p]
            if midi_out_ports:
                return midi_out_ports[0]

            # Windows: prefer MIDIIN2 (LPMiniMK3 MIDI) which carries note messages
            midiin2_ports = [p for p in matching_ports if "MIDIIN2" in p and "LPMiniMK3" in p]
            if midiin2_ports:
                return midiin2_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # Check if this is a Pro MK3 (uses MIDI 0 for note messages, not MIDI 1!)
        if any("LPProMK3" in p for p in matching_ports):
            # macOS: prefer ports ending in "MIDI Out" (not "DAW Out")
            midi_out_ports = [p for p in matching_ports if "MIDI Out" in p and "DAW" not in p]
            if midi_out_ports:
                return midi_out_ports[0]

            # Windows: prefer "LPProMK3 MIDI 0" which carries note messages
            midi0_ports = [p for p in matching_ports if "LPProMK3 MIDI 0" in p]
            if midi0_ports:
                return midi0_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # For other Launchpad models (X, etc.)
        # macOS: prefer ports ending in "MIDI Out"
        midi_out_ports = [p for p in matching_ports if "MIDI Out" in p]
        if midi_out_ports:
            return midi_out_ports[0]

        # Windows/other: prefer "MIDI 1"
        midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
        if midi1_ports:
            return midi1_ports[0]

        # Fall back to first match
        return matching_ports[0]

    @staticmethod
    def select_output_port(matching_ports: list[str]) -> Optional[str]:
        """
        Select the best output port from matching Launchpad ports.

        Launchpad devices have multiple MIDI ports with different naming conventions:

        Windows:
        - Launchpad Pro MK3: Note messages on "LPProMK3 MIDI 0" (uses port 0, not port 1!)
        - Launchpad Mini MK3: Note messages on "MIDIOUT2 (LPMiniMK3 MIDI) 1" (uses MIDIOUT2)

        macOS:
        - Launchpad Mini MK3: "Launchpad Mini MK3 LPMiniMK3 MIDI In" for output (not DAW In)
        - Note: On macOS, output ports end with "In" (they input FROM the computer)

        Args:
            matching_ports: List of port names that match Launchpad patterns

        Returns:
            Selected port name, or None if list is empty
        """
        if not matching_ports:
            return None

        # Check if this is a Mini MK3
        if any("LPMiniMK3" in p for p in matching_ports):
            # macOS: prefer ports ending in "MIDI In" (not "DAW In")
            midi_in_ports = [p for p in matching_ports if "MIDI In" in p and "DAW" not in p]
            if midi_in_ports:
                return midi_in_ports[0]

            # Windows: prefer MIDIOUT2 (LPMiniMK3 MIDI) which carries note messages
            midiout2_ports = [p for p in matching_ports if "MIDIOUT2" in p and "LPMiniMK3" in p]
            if midiout2_ports:
                return midiout2_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # Check if this is a Pro MK3 (uses MIDI 0 for note messages, not MIDI 1!)
        if any("LPProMK3" in p for p in matching_ports):
            # macOS: prefer ports ending in "MIDI In" (not "DAW In")
            midi_in_ports = [p for p in matching_ports if "MIDI In" in p and "DAW" not in p]
            if midi_in_ports:
                return midi_in_ports[0]

            # Windows: prefer "LPProMK3 MIDI 0" which carries note messages
            midi0_ports = [p for p in matching_ports if "LPProMK3 MIDI 0" in p]
            if midi0_ports:
                return midi0_ports[0]

            # Fall back to ports with "MIDI 1" in the name
            midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
            if midi1_ports:
                return midi1_ports[0]

        # For other Launchpad models (X, etc.)
        # macOS: prefer ports ending in "MIDI In"
        midi_in_ports = [p for p in matching_ports if "MIDI In" in p]
        if midi_in_ports:
            return midi_in_ports[0]

        # Windows/other: prefer "MIDI 1"
        midi1_ports = [p for p in matching_ports if "MIDI 1" in p]
        if midi1_ports:
            return midi1_ports[0]

        # Fall back to first match
        return matching_ports[0]

