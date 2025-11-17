"""Launchsampler: Audio sampler for MIDI pad controllers."""

__version__ = "0.1.0"

# Core engine
from .core import SamplerEngine

# Device controllers
from .devices import DeviceController, LaunchpadController  # LaunchpadController is deprecated alias

__all__ = [
    "SamplerEngine",
    "DeviceController",
    "LaunchpadController",  # Deprecated, use DeviceController
]
