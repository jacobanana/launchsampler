"""Generic device protocols and abstractions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from launchsampler.models import Color


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

    def parse_message(self, msg) -> DeviceEvent | None:
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

    def set_led(self, index: int, color: Color) -> None:
        """
        Set single LED color.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (each channel 0-127)

        Note:
            Device implementation chooses whether to use RGB or convert to palette.
        """
        ...

    def set_leds(self, updates: list[tuple[int, Color]]) -> None:
        """
        Set multiple LEDs efficiently.

        Args:
            updates: List of (logical_index, color) tuples

        Note:
            Device implementation chooses whether to use RGB or convert to palette.
        """
        ...

    def clear_all(self) -> None:
        """Clear all LEDs (turn off)."""
        ...

    def set_led_flashing(self, index: int, color: Color) -> None:
        """
        Set LED to flash/blink animation.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (device converts to palette internally)

        Note:
            Device implementation converts RGB to nearest palette color.
        """
        ...

    def set_led_pulsing(self, index: int, color: Color) -> None:
        """
        Set LED to pulse/breathe animation.

        Args:
            index: Logical pad index (0-63)
            color: RGB color object (device converts to palette internally)

        Note:
            Device implementation converts RGB to nearest palette color.
        """
        ...

    def set_control_led(self, control: int, color: Color) -> None:
        """
        Set control button LED (non-pad buttons) using RGB mode.

        Args:
            control: Control button identifier (device-specific, e.g., CC number)
            color: RGB color object (each channel 0-255)

        Note:
            Device implementation converts 8-bit RGB to 7-bit for MIDI.
        """
        ...

    def set_control_led_static(self, control: int, palette_index: int) -> None:
        """
        Set control button LED using palette index (static mode).

        Args:
            control: Control button identifier (device-specific, e.g., CC number)
            palette_index: Palette color index (0-127)
        """
        ...
