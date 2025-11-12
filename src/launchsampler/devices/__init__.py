"""Device-specific implementations for different MIDI controllers."""

from .launchpad import LaunchpadController, LaunchpadDevice

__all__ = ["LaunchpadController", "LaunchpadDevice"]
