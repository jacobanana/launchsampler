"""Device registry using Pydantic models for configuration validation."""

import logging
from pathlib import Path
from typing import Optional

from .schema import DeviceRegistrySchema, DeviceFamily, Device, OSPortSelection
from .config import DeviceConfig

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """
    Registry of all supported MIDI devices.

    Loads device configurations from JSON using Pydantic validation
    and provides device detection and instantiation services.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize device registry.

        Args:
            config_path: Path to devices.json config file.
                        If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "devices.json"

        self.config_path = config_path
        self.schema: DeviceRegistrySchema = self._load_schema()
        self.devices: list[DeviceConfig] = self._flatten_configs()

    def _load_schema(self) -> DeviceRegistrySchema:
        """Load and validate device registry schema from JSON."""
        try:
            schema = DeviceRegistrySchema.from_json_file(self.config_path)
            logger.info(f"Validated device registry from {self.config_path}")
            return schema
        except Exception as e:
            logger.error(f"Failed to load device config from {self.config_path}: {e}")
            raise

    def _flatten_configs(self) -> list[DeviceConfig]:
        """Flatten family + device configs into runtime DeviceConfigs."""
        configs = []

        for family in self.schema.families:
            for device in family.devices:
                # Merge family defaults with device overrides
                config = self._merge_family_and_device(family, device)
                configs.append(config)

        logger.info(f"Loaded {len(configs)} device configurations")
        return configs

    def _merge_family_and_device(
        self,
        family: DeviceFamily,
        device: Device
    ) -> DeviceConfig:
        """
        Merge family and device configs into a single DeviceConfig.

        Args:
            family: Device family configuration
            device: Specific device configuration

        Returns:
            Merged DeviceConfig for runtime use
        """
        # Merge detection patterns (family + device, deduplicated)
        all_patterns = list(set(family.detection_patterns + device.detection_patterns))

        # Merge port selection rules (device overrides family)
        input_rules = self._merge_port_rules(
            family.input_port_selection,
            device.overrides.input_port_selection
        )
        output_rules = self._merge_port_rules(
            family.output_port_selection,
            device.overrides.output_port_selection
        )

        return DeviceConfig(
            family=family.family,
            model=device.model,
            manufacturer=family.manufacturer,
            implements=family.implements,
            detection_patterns=all_patterns,
            capabilities=family.capabilities,
            input_port_selection=input_rules,
            output_port_selection=output_rules,
            sysex_header=device.sysex_header
        )

    def _merge_port_rules(
        self,
        base: OSPortSelection,
        override: Optional[OSPortSelection]
    ) -> OSPortSelection:
        """
        Merge port selection rules with overrides.

        Args:
            base: Base rules from family
            override: Override rules from device (if any)

        Returns:
            Merged OSPortSelection
        """
        if override is None:
            return base

        # For each OS, use override if it has preferences, otherwise use base
        return OSPortSelection(
            windows=override.windows if override.windows.prefer else base.windows,
            darwin=override.darwin if override.darwin.prefer else base.darwin,
            linux=override.linux if override.linux.prefer else base.linux
        )

    def detect_device(self, port_name: str) -> Optional[DeviceConfig]:
        """
        Detect which device config matches a port name.

        Args:
            port_name: MIDI port name string

        Returns:
            Matching DeviceConfig or None if no match found
        """
        for config in self.devices:
            if config.matches(port_name):
                logger.debug(f"Detected {config.model} from port: {port_name}")
                return config

        logger.debug(f"No device matched port: {port_name}")
        return None

    def get_all_patterns(self) -> list[str]:
        """
        Get all detection patterns across all devices.

        Useful for creating a device_filter function for MidiManager.

        Returns:
            List of all detection patterns
        """
        patterns = set()
        for config in self.devices:
            patterns.update(config.detection_patterns)
        return list(patterns)

    def matches_any_device(self, port_name: str) -> bool:
        """
        Check if port name matches any registered device.

        Args:
            port_name: MIDI port name string

        Returns:
            True if port matches any device
        """
        return self.detect_device(port_name) is not None

    def create_device(self, config: DeviceConfig, midi_manager):
        """
        Create a device instance from configuration.

        Args:
            config: Device configuration
            midi_manager: MIDI manager instance

        Returns:
            GenericDevice instance

        Raises:
            ValueError: If implementation not found
        """
        from .adapters import get_adapter
        from .device import GenericDevice
        from .input import GenericInput

        # Look up adapter classes
        adapter = get_adapter(config.implements)
        if adapter is None:
            raise ValueError(f"Unknown adapter: {config.implements}")

        MapperClass, OutputClass = adapter

        # Instantiate device-specific components
        mapper = MapperClass(config)
        input_handler = GenericInput(mapper)
        output_handler = OutputClass(midi_manager, config)

        # Wrap in GenericDevice
        return GenericDevice(config, input_handler, output_handler)


# Singleton instance
_registry: Optional[DeviceRegistry] = None


def get_registry() -> DeviceRegistry:
    """Get singleton DeviceRegistry instance."""
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry
