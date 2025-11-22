"""Pydantic models for device configuration schema.

This module defines the structure of the devices.json configuration file
using Pydantic v2 for type safety and validation.
"""

import platform
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class PortSelectionRules(BaseModel):
    """Port selection rules for a specific OS."""

    prefer: list[str] = Field(
        default_factory=list, description="Port patterns to prefer in order of priority"
    )
    exclude: list[str] = Field(default_factory=list, description="Port patterns to exclude")
    fallback: str | None = Field(
        None, description="Last resort pattern if preferred patterns don't match"
    )


class OSPortSelection(BaseModel):
    """OS-specific port selection rules."""

    # Mypy doesn't recognize Pydantic models as valid callables for default_factory
    windows: PortSelectionRules = Field(default_factory=PortSelectionRules)  # type: ignore[arg-type]
    darwin: PortSelectionRules = Field(default_factory=PortSelectionRules)  # type: ignore[arg-type]
    linux: PortSelectionRules = Field(default_factory=PortSelectionRules)  # type: ignore[arg-type]

    def get_for_current_os(self) -> PortSelectionRules:
        """Get rules for current operating system."""
        os_name = platform.system().lower()
        # Mypy incorrectly thinks fallback is required despite having a default
        return getattr(self, os_name, PortSelectionRules())  # type: ignore[call-arg]


class DeviceCapabilities(BaseModel):
    """Device hardware capabilities."""

    num_pads: int = Field(ge=1, description="Number of pads on the device")
    grid_size: int = Field(ge=1, description="Grid size (e.g., 8 for 8x8 grid)")
    supports_sysex: bool = Field(default=True, description="Whether device supports SysEx messages")
    supports_rgb: bool = Field(default=True, description="Whether device supports RGB colors")


class DeviceOverrides(BaseModel):
    """Device-specific overrides for family defaults."""

    input_port_selection: OSPortSelection | None = None
    output_port_selection: OSPortSelection | None = None


class Device(BaseModel):
    """Individual device configuration within a family."""

    model: str = Field(min_length=1, description="Device model name (e.g., 'Launchpad Mini MK3')")
    detection_patterns: list[str] = Field(
        default_factory=list, description="Additional patterns for detecting this specific device"
    )
    sysex_header: list[int] | None = Field(
        None, description="SysEx header bytes for this device (excluding F0)"
    )
    overrides: DeviceOverrides = Field(
        default_factory=DeviceOverrides, description="Device-specific overrides"
    )

    @field_validator("sysex_header")
    @classmethod
    def validate_sysex_header(cls, v: list[int] | None) -> list[int] | None:
        """Validate SysEx header bytes are in valid range."""
        if v is not None:
            for byte in v:
                if not 0 <= byte <= 127:
                    raise ValueError(f"SysEx byte {byte} out of range (0-127)")
        return v


class DeviceFamily(BaseModel):
    """Device family configuration (e.g., Launchpad MK3 family)."""

    family: str = Field(min_length=1, description="Family identifier (e.g., 'launchpad_mk3')")
    manufacturer: str = Field(min_length=1, description="Manufacturer name (e.g., 'Novation')")
    implements: str = Field(
        min_length=1, description="Implementation name mapping to Python classes"
    )
    detection_patterns: list[str] = Field(
        default_factory=list, description="Common patterns for detecting any device in this family"
    )
    capabilities: DeviceCapabilities = Field(description="Hardware capabilities shared by family")
    input_port_selection: OSPortSelection = Field(
        default_factory=OSPortSelection, description="Default input port selection rules for family"
    )
    output_port_selection: OSPortSelection = Field(
        default_factory=OSPortSelection,
        description="Default output port selection rules for family",
    )
    devices: list[Device] = Field(
        default_factory=list, description="List of specific devices in this family"
    )


class DeviceRegistrySchema(BaseModel):
    """Root schema for the devices.json configuration file."""

    families: list[DeviceFamily] = Field(
        default_factory=list, description="List of device families"
    )

    @classmethod
    def from_json_file(cls, path: Path) -> "DeviceRegistrySchema":
        """Load registry from JSON file with validation."""
        with open(path) as f:
            return cls.model_validate_json(f.read())

    def to_json_file(self, path: Path, indent: int = 2) -> None:
        """Save registry to JSON file."""
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=indent))

    @classmethod
    def generate_json_schema(cls, path: Path) -> None:
        """Generate JSON schema for documentation and IDE support."""
        import json

        schema = cls.model_json_schema()
        with open(path, "w") as f:
            json.dump(schema, f, indent=2)
