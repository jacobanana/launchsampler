"""Generic device infrastructure for grid-based MIDI controllers."""

from .controller import DeviceController
from .protocols import (
    DeviceEvent,
    PadPressEvent,
    PadReleaseEvent,
    DeviceInput,
    DeviceOutput,
    Device,
)

# Backward compatibility alias
LaunchpadController = DeviceController

__all__ = [
    "DeviceController",
    "LaunchpadController",  # Deprecated
    "DeviceEvent",
    "PadPressEvent",
    "PadReleaseEvent",
    "DeviceInput",
    "DeviceOutput",
    "Device",
]
