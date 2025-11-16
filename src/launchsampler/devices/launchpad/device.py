"""Launchpad device protocol and message parsing."""

import logging
from typing import Optional, Tuple

import mido

from launchsampler.models import Color

logger = logging.getLogger(__name__)


class LaunchpadDevice:
    """
    Launchpad device protocol.

    Defines Launchpad-specific patterns, message parsing, and LED control.
    Pure functions - no state, just protocol knowledge.
    """

    # Launchpad hardware constants
    NUM_PADS = 64  # 8x8 grid
    GRID_SIZE = 8  # 8x8 grid

    # Launchpad device name patterns to detect
    PATTERNS = [
        "Launchpad X",
        "Launchpad Mini",
        "Launchpad Pro",
        "LPProMK3",  # Launchpad Pro MK3
        "LPMiniMK3",  # Launchpad Mini MK3
        "LPX",  # Launchpad X
        "Launchpad",
    ]

    @staticmethod
    def matches(port_name: str) -> bool:
        """
        Check if port name matches a Launchpad device.

        Args:
            port_name: MIDI port name

        Returns:
            True if port matches any Launchpad pattern
        """
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

    @staticmethod
    def parse_input(msg: mido.Message) -> Optional[Tuple[str, int]]:
        """
        Parse incoming MIDI message into Launchpad events.

        Args:
            msg: MIDI message

        Returns:
            Tuple of (event_type, pad_index) or None
            event_type: "pad_press" or "pad_release"
            pad_index: 0-63
        """
        # Filter out clock messages
        if msg.type == 'clock':
            return None

        # Handle note on/off
        if msg.type == 'note_on':
            # Note on with velocity 0 is actually note off
            if msg.velocity > 0:
                # Launchpad uses notes 0-63 for the 8x8 grid
                if 0 <= msg.note < LaunchpadDevice.NUM_PADS:
                    return ("pad_press", msg.note)
            else:
                if 0 <= msg.note < LaunchpadDevice.NUM_PADS:
                    return ("pad_release", msg.note)

        elif msg.type == 'note_off':
            if 0 <= msg.note < LaunchpadDevice.NUM_PADS:
                return ("pad_release", msg.note)

        return None

    @staticmethod
    def create_led_message(pad_index: int, color: Color) -> mido.Message:
        """
        Create MIDI message to set pad LED color.

        Note: This is a placeholder implementation. Actual LED control
        depends on the specific Launchpad model and requires SysEx messages.

        Args:
            pad_index: Pad 0-63
            color: RGB color

        Returns:
            MIDI message to send
        """
        # TODO: Implement proper SysEx messages for LED control
        # For now, this is a placeholder that won't actually work
        logger.warning("LED control not yet implemented")
        return mido.Message('note_on', note=pad_index, velocity=127)
