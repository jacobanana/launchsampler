"""Generic device implementation using config-driven architecture."""

import logging
from typing import Optional
from launchsampler.midi import MidiManager
from .protocols import DeviceInput, DeviceOutput
from .config import DeviceConfig
from .input import GenericInput

logger = logging.getLogger(__name__)


class GenericDevice:
    """
    Generic MIDI device implementation.

    Composes generic input parsing with device-specific
    output control and note mapping, configured via DeviceConfig.
    """

    def __init__(
        self,
        config: DeviceConfig,
        input_handler: DeviceInput,
        output_handler: DeviceOutput
    ):
        """
        Initialize generic device.

        Args:
            config: Device configuration
            input_handler: Device input parser (usually GenericInput with device mapper)
            output_handler: Device-specific output controller
        """
        self.config = config
        self._input = input_handler
        self._output = output_handler

    @property
    def input(self) -> DeviceInput:
        """Get input handler."""
        return self._input

    @property
    def output(self) -> DeviceOutput:
        """Get output controller."""
        return self._output

    @property
    def num_pads(self) -> int:
        """Get number of pads on this device."""
        return self.config.num_pads

    @property
    def grid_size(self) -> int:
        """Get grid size."""
        return self.config.grid_size

    @property
    def display_name(self) -> str:
        """Get human-readable device name."""
        return self.config.display_name

    @staticmethod
    def matches(port_name: str, config: DeviceConfig) -> bool:
        """Check if port name matches device."""
        return config.matches(port_name)

    @staticmethod
    def select_input_port(matching_ports: list[str], config: DeviceConfig) -> Optional[str]:
        """Select best input port using device config."""
        return config.select_input_port(matching_ports)

    @staticmethod
    def select_output_port(matching_ports: list[str], config: DeviceConfig) -> Optional[str]:
        """Select best output port using device config."""
        return config.select_output_port(matching_ports)
