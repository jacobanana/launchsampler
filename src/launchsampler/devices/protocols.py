"""Generic device protocols and abstractions."""

from abc import ABC, abstractmethod
from typing import Protocol, Optional, Tuple, List
from enum import Enum


class DeviceEvent:
    """Generic device event (input from hardware)."""
    pass


class PadPressEvent(DeviceEvent):
    """Pad was pressed."""
    def __init__(self, pad_index: int, velocity: int):
        self.pad_index = pad_index  # Logical 0-63
        self.velocity = velocity


class PadReleaseEvent(DeviceEvent):
    """Pad was released."""
    def __init__(self, pad_index: int):
        self.pad_index = pad_index  # Logical 0-63


class ControlChangeEvent(DeviceEvent):
    """MIDI control change received."""
    def __init__(self, control: int, value: int):
        self.control = control
        self.value = value


class DeviceInput(Protocol):
    """Protocol for device input handling."""

    def parse_message(self, msg) -> Optional[DeviceEvent]:
        """
        Parse incoming message into device event.

        Must handle hardware-specific note mapping internally and
        return events with logical pad indices (0-63).
        """
        ...


class DeviceOutput(Protocol):
    """Protocol for device output/display control."""

    def initialize(self) -> None:
        """Initialize the output device."""
        ...

    def shutdown(self) -> None:
        """Shutdown and cleanup."""
        ...

    def set_led(self, index: int, color: 'Color') -> None:
        """
        Set single LED by logical index.

        Args:
            index: Logical pad index (0-63)
            color: RGB color
        """
        ...

    def set_leds_bulk(self, updates: List[Tuple[int, 'Color']]) -> None:
        """
        Set multiple LEDs efficiently.

        Args:
            updates: List of (logical_index, color) tuples
        """
        ...

    def clear_all(self) -> None:
        """Clear all LEDs."""
        ...
