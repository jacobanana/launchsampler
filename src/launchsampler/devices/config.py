"""Device configuration class for config-driven device detection and port selection."""

import platform
from typing import Optional
from dataclasses import dataclass


@dataclass
class DeviceConfig:
    """
    Configuration for a specific MIDI device.

    Represents a merged configuration from family + device-specific settings.
    Handles device detection and OS-specific port selection.
    """

    # Identity
    family: str
    model: str
    manufacturer: str
    implements: str

    # Detection
    detection_patterns: list[str]

    # Capabilities
    capabilities: dict

    # Port selection rules (OS -> rules dict)
    input_port_selection: dict[str, dict]
    output_port_selection: dict[str, dict]

    # Device-specific metadata
    sysex_header: Optional[list[int]] = None

    def matches(self, port_name: str) -> bool:
        """Check if port name matches this device's detection patterns."""
        return any(pattern in port_name for pattern in self.detection_patterns)

    def select_input_port(self, matching_ports: list[str]) -> Optional[str]:
        """
        Select best input port from matching ports using OS-specific rules.

        Args:
            matching_ports: List of port names that already match detection patterns

        Returns:
            Selected port name or None if list is empty
        """
        if not matching_ports:
            return None

        system = platform.system().lower()
        rules = self.input_port_selection.get(system, {})

        return self._apply_port_rules(matching_ports, rules)

    def select_output_port(self, matching_ports: list[str]) -> Optional[str]:
        """
        Select best output port from matching ports using OS-specific rules.

        Args:
            matching_ports: List of port names that already match detection patterns

        Returns:
            Selected port name or None if list is empty
        """
        if not matching_ports:
            return None

        system = platform.system().lower()
        rules = self.output_port_selection.get(system, {})

        return self._apply_port_rules(matching_ports, rules)

    def _apply_port_rules(self, ports: list[str], rules: dict) -> Optional[str]:
        """
        Apply port selection rules to find best matching port.

        Rules format:
        {
            "prefer": ["pattern1", "pattern2"],  # Try these patterns in order
            "exclude": ["pattern"],              # Exclude ports matching this
            "fallback": "pattern"                # Last resort pattern
        }

        Args:
            ports: List of available port names
            rules: Port selection rules dictionary

        Returns:
            Selected port name or first port if no rules match
        """
        if not ports:
            return None

        # Get rule components
        prefer_patterns = rules.get("prefer", [])
        exclude_patterns = rules.get("exclude", [])
        fallback_pattern = rules.get("fallback")

        # First, try preferred patterns in order
        for pattern in prefer_patterns:
            # If prefer is a list of patterns, all must match
            if isinstance(pattern, list):
                result = self._first_matching_all(ports, pattern, exclude_patterns)
                if result:
                    return result
            else:
                result = self._first_matching(ports, [pattern], exclude_patterns)
                if result:
                    return result

        # Try fallback pattern if specified
        if fallback_pattern:
            result = self._first_matching(ports, [fallback_pattern], exclude_patterns)
            if result:
                return result

        # Last resort: return first port that doesn't match exclusions
        if exclude_patterns:
            for port in ports:
                if not any(excl in port for excl in exclude_patterns):
                    return port

        # Absolute fallback: just return first port
        return ports[0]

    def _first_matching(self, ports: list[str], patterns: list[str], exclude: list[str]) -> Optional[str]:
        """Find first port matching any pattern and not matching exclusions."""
        for port in ports:
            # Check if port matches any exclude pattern
            if any(excl in port for excl in exclude):
                continue

            # Check if port matches any include pattern
            if any(pattern in port for pattern in patterns):
                return port

        return None

    def _first_matching_all(self, ports: list[str], patterns: list[str], exclude: list[str]) -> Optional[str]:
        """Find first port matching ALL patterns and not matching exclusions."""
        for port in ports:
            # Check if port matches any exclude pattern
            if any(excl in port for excl in exclude):
                continue

            # Check if port matches ALL include patterns
            if all(pattern in port for pattern in patterns):
                return port

        return None

    @property
    def display_name(self) -> str:
        """Get human-readable device name."""
        return self.model

    @property
    def num_pads(self) -> int:
        """Get number of pads on this device."""
        return self.capabilities.get("num_pads", 0)

    @property
    def grid_size(self) -> int:
        """Get grid size (e.g., 8 for 8x8)."""
        return self.capabilities.get("grid_size", 0)
