"""Pydantic-based device configuration for runtime use.

This module defines DeviceConfig, which is the flattened runtime representation
created by merging family defaults with device-specific overrides.
"""

from typing import Optional
from pydantic import BaseModel, Field, computed_field
from .schema import DeviceCapabilities, OSPortSelection, PortSelectionRules


class DeviceConfig(BaseModel):
    """
    Flattened device configuration (family + device merged).

    This is the runtime representation used by the application.
    Created by merging family defaults with device-specific overrides.
    """

    # Identity
    family: str = Field(description="Device family identifier")
    model: str = Field(description="Device model name")
    manufacturer: str = Field(description="Manufacturer name")
    implements: str = Field(description="Implementation name for adapter lookup")

    # Detection
    detection_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns for detecting this device in port names"
    )

    # Capabilities
    capabilities: DeviceCapabilities = Field(
        description="Device hardware capabilities"
    )

    # Port selection (merged family + device rules)
    input_port_selection: OSPortSelection = Field(
        default_factory=OSPortSelection,
        description="Input port selection rules"
    )
    output_port_selection: OSPortSelection = Field(
        default_factory=OSPortSelection,
        description="Output port selection rules"
    )

    # Device-specific metadata
    sysex_header: Optional[list[int]] = Field(
        None,
        description="SysEx header bytes for device control"
    )

    # Computed properties for backward compatibility
    @computed_field
    @property
    def display_name(self) -> str:
        """Human-readable device name."""
        return self.model

    @computed_field
    @property
    def num_pads(self) -> int:
        """Number of pads on device."""
        return self.capabilities.num_pads

    @computed_field
    @property
    def grid_size(self) -> int:
        """Grid size."""
        return self.capabilities.grid_size

    # Methods for device detection and port selection
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

        rules = self.input_port_selection.get_for_current_os()
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

        rules = self.output_port_selection.get_for_current_os()
        return self._apply_port_rules(matching_ports, rules)

    def _apply_port_rules(
        self,
        ports: list[str],
        rules: PortSelectionRules
    ) -> Optional[str]:
        """
        Apply port selection rules to find best matching port.

        Args:
            ports: List of available port names
            rules: Port selection rules

        Returns:
            Selected port name or first port if no rules match
        """
        if not ports:
            return None

        # First, try preferred patterns in order
        for pattern in rules.prefer:
            # If prefer is a list of patterns, all must match
            if isinstance(pattern, list):
                result = self._first_matching_all(ports, pattern, rules.exclude)
                if result:
                    return result
            else:
                result = self._first_matching(ports, [pattern], rules.exclude)
                if result:
                    return result

        # Try fallback pattern if specified
        if rules.fallback:
            result = self._first_matching(ports, [rules.fallback], rules.exclude)
            if result:
                return result

        # Last resort: return first port that doesn't match exclusions
        if rules.exclude:
            for port in ports:
                if not any(excl in port for excl in rules.exclude):
                    return port

        # Absolute fallback: just return first port
        return ports[0]

    def _first_matching(
        self,
        ports: list[str],
        patterns: list[str],
        exclude: list[str]
    ) -> Optional[str]:
        """Find first port matching any pattern and not matching exclusions."""
        for port in ports:
            # Check if port matches any exclude pattern
            if any(excl in port for excl in exclude):
                continue

            # Check if port matches any include pattern
            if any(pattern in port for pattern in patterns):
                return port

        return None

    def _first_matching_all(
        self,
        ports: list[str],
        patterns: list[str],
        exclude: list[str]
    ) -> Optional[str]:
        """Find first port matching ALL patterns and not matching exclusions."""
        for port in ports:
            # Check if port matches any exclude pattern
            if any(excl in port for excl in exclude):
                continue

            # Check if port matches ALL include patterns
            if all(pattern in port for pattern in patterns):
                return port

        return None
