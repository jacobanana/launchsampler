"""Device adapter registry.

Maps adapter names (from config) to concrete device-specific classes.
Adapters translate between generic device protocols and hardware-specific
MIDI messages, note mappings, and LED control.
"""

from typing import Optional, Type, Tuple
from ..protocols import DeviceOutput
from ..input import NoteMapper


# Type for adapter tuple (Mapper, Output)
Adapter = Tuple[Type[NoteMapper], Type[DeviceOutput]]


# Registry of adapters
# Format: "AdapterName": (MapperClass, OutputClass)
ADAPTERS: dict[str, Adapter] = {}


def register_adapter(name: str, mapper_class: Type[NoteMapper], output_class: Type[DeviceOutput]) -> None:
    """
    Register a device adapter.

    Args:
        name: Adapter name (matches "implements" field in config)
        mapper_class: Note mapper class
        output_class: Output controller class
    """
    ADAPTERS[name] = (mapper_class, output_class)


def get_adapter(name: str) -> Optional[Adapter]:
    """
    Get adapter classes by name.

    Args:
        name: Adapter name from config

    Returns:
        Tuple of (MapperClass, OutputClass) or None if not found
    """
    return ADAPTERS.get(name)


# Register built-in adapters
from .launchpad_mk3 import LaunchpadMK3Mapper, LaunchpadMK3Output

register_adapter("LaunchpadMK3", LaunchpadMK3Mapper, LaunchpadMK3Output)
