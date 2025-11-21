"""Device adapter registry.

Maps adapter names (from config) to concrete device-specific classes.
Adapters translate between generic device protocols and hardware-specific
MIDI messages, note mappings, and LED control.
"""

from ..input import NoteMapper
from ..protocols import DeviceOutput

# Type for adapter tuple (Mapper, Output)
Adapter = tuple[type[NoteMapper], type[DeviceOutput]]


# Registry of adapters
# Format: "AdapterName": (MapperClass, OutputClass)
ADAPTERS: dict[str, Adapter] = {}


def register_adapter(
    name: str, mapper_class: type[NoteMapper], output_class: type[DeviceOutput]
) -> None:
    """
    Register a device adapter.

    Args:
        name: Adapter name (matches "implements" field in config)
        mapper_class: Note mapper class
        output_class: Output controller class
    """
    ADAPTERS[name] = (mapper_class, output_class)


def get_adapter(name: str) -> Adapter | None:
    """
    Get adapter classes by name.

    Args:
        name: Adapter name from config

    Returns:
        Tuple of (MapperClass, OutputClass) or None if not found
    """
    return ADAPTERS.get(name)


def _register_builtin_adapters() -> None:
    """Register built-in adapters. Called on module import."""
    from .launchpad_mk3 import LaunchpadMK3Mapper, LaunchpadMK3Output

    register_adapter("LaunchpadMK3", LaunchpadMK3Mapper, LaunchpadMK3Output)


# Register built-in adapters on module import
_register_builtin_adapters()
