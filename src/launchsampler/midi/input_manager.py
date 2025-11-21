"""Generic MIDI input manager with hot-plug support."""

import logging
from collections.abc import Callable

import mido

from .base_manager import BaseMidiManager

logger = logging.getLogger(__name__)


class MidiInputManager(BaseMidiManager[mido.ports.BaseInput]):
    """
    Generic MIDI input manager with hot-plug support.

    Monitors for MIDI input devices matching a filter function,
    automatically connects/reconnects when devices are plugged/unplugged.
    """

    def __init__(
        self,
        device_filter: Callable[[str], bool],
        poll_interval: float = 5.0,
        port_selector: Callable[[list[str]], str | None] | None = None,
    ):
        """
        Initialize MIDI input manager.

        Args:
            device_filter: Function that returns True if port name matches desired device
            poll_interval: How often to check for device changes (seconds)
            port_selector: Optional function to select best port from candidates.
                          If None, selects first matching port.
        """
        super().__init__(device_filter, poll_interval, port_selector)
        self._message_callback: Callable[[mido.Message], None] | None = None

    def on_message(self, callback: Callable[[mido.Message], None]) -> None:
        """
        Register callback for incoming MIDI messages.

        Callback is executed in mido's internal I/O thread - keep it fast!

        Args:
            callback: Function that receives mido.Message
        """
        self._message_callback = callback

    def _get_available_ports(self) -> list[str]:
        """Get list of available MIDI input ports."""
        return mido.get_input_names()

    def _open_port(self, port_name: str) -> mido.ports.BaseInput:
        """
        Open a MIDI input port with callback.

        Args:
            port_name: Name of the port to open

        Returns:
            Opened MIDI input port

        Raises:
            Exception: If port cannot be opened
        """
        return mido.open_input(port_name, callback=self._midi_callback)

    def _get_port_type_name(self) -> str:
        """Get port type name for logging."""
        return "input"

    def _get_log_level_for_port_changes(self) -> int:
        """Get logging level for port connection/disconnection events."""
        return logging.INFO

    def _midi_callback(self, msg: mido.Message) -> None:
        """
        MIDI message callback - called from mido's internal I/O thread.

        Dispatches to user's registered callback if set.
        """
        try:
            if self._message_callback:
                self._message_callback(msg)
        except Exception as e:
            logger.error(f"Error in MIDI input callback: {e}")
