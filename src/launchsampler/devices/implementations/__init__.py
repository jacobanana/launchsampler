"""Device implementation registry.

Maps implementation names (from config) to concrete classes.
"""

from typing import Optional, Type, Tuple
from ..protocols import DeviceOutput
from ..input import NoteMapper


# Type for implementation tuple (Mapper, Output)
Implementation = Tuple[Type[NoteMapper], Type[DeviceOutput]]


# Registry of implementations
# Format: "ImplementationName": (MapperClass, OutputClass)
IMPLEMENTATIONS: dict[str, Implementation] = {}


def register_implementation(name: str, mapper_class: Type[NoteMapper], output_class: Type[DeviceOutput]) -> None:
    """
    Register a device implementation.

    Args:
        name: Implementation name (matches "implements" field in config)
        mapper_class: Note mapper class
        output_class: Output controller class
    """
    IMPLEMENTATIONS[name] = (mapper_class, output_class)


def get_implementation(name: str) -> Optional[Implementation]:
    """
    Get implementation classes by name.

    Args:
        name: Implementation name from config

    Returns:
        Tuple of (MapperClass, OutputClass) or None if not found
    """
    return IMPLEMENTATIONS.get(name)


# Register built-in implementations
from .launchpad_mk3 import LaunchpadMK3Mapper, LaunchpadMK3Output

register_implementation("LaunchpadMK3", LaunchpadMK3Mapper, LaunchpadMK3Output)
