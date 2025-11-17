"""Device registry for loading and managing device configurations."""

import json
import logging
from pathlib import Path
from typing import Optional
from .config import DeviceConfig
from .adapters import get_adapter
from .device import GenericDevice
from .input import GenericInput


logger = logging.getLogger(__name__)


class DeviceRegistry:
    """
    Registry of all supported MIDI devices.

    Loads device configurations from JSON and provides
    device detection and instantiation services.
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
        self.devices: list[DeviceConfig] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load device configurations from JSON file."""
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            # Parse families and devices
            for family_data in data.get("families", []):
                family_name = family_data["family"]
                manufacturer = family_data["manufacturer"]
                implements = family_data["implements"]
                family_patterns = family_data.get("detection_patterns", [])
                capabilities = family_data.get("capabilities", {})
                family_input_rules = family_data.get("input_port_selection", {})
                family_output_rules = family_data.get("output_port_selection", {})

                # Process each device in the family
                for device_data in family_data.get("devices", []):
                    model = device_data["model"]
                    device_patterns = device_data.get("detection_patterns", [])
                    sysex_header = device_data.get("sysex_header")

                    # Merge detection patterns (family + device)
                    all_patterns = list(set(family_patterns + device_patterns))

                    # Merge port selection rules (device overrides family)
                    overrides = device_data.get("overrides", {})
                    input_rules = self._merge_rules(
                        family_input_rules,
                        overrides.get("input_port_selection", {})
                    )
                    output_rules = self._merge_rules(
                        family_output_rules,
                        overrides.get("output_port_selection", {})
                    )

                    # Create device config
                    config = DeviceConfig(
                        family=family_name,
                        model=model,
                        manufacturer=manufacturer,
                        implements=implements,
                        detection_patterns=all_patterns,
                        capabilities=capabilities,
                        input_port_selection=input_rules,
                        output_port_selection=output_rules,
                        sysex_header=sysex_header
                    )

                    self.devices.append(config)

            logger.info(f"Loaded {len(self.devices)} device configurations")

        except Exception as e:
            logger.error(f"Failed to load device config from {self.config_path}: {e}")
            raise

    def _merge_rules(self, base_rules: dict, override_rules: dict) -> dict:
        """
        Merge port selection rules with overrides.

        Args:
            base_rules: Base rules from family
            override_rules: Override rules from device

        Returns:
            Merged rules dictionary
        """
        merged = dict(base_rules)

        for os_name, os_rules in override_rules.items():
            if os_name in merged:
                # Merge OS-specific rules
                merged[os_name] = {**merged[os_name], **os_rules}
            else:
                # Add new OS rules
                merged[os_name] = os_rules

        return merged

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
