"""Generic MIDI manager combining input and output."""

import logging
from typing import Callable, Optional

import mido

from .input_manager import MidiInputManager
from .output_manager import MidiOutputManager

logger = logging.getLogger(__name__)


class MidiManager:
    """
    Generic MIDI manager combining input and output functionality.

    Provides a unified interface for MIDI device management with hot-plug support.
    """

    def __init__(
        self,
        device_filter: Callable[[str], bool],
        poll_interval: float = 5.0,
        port_selector: Optional[Callable[[list[str]], Optional[str]]] = None
    ):
        """
        Initialize MIDI manager.

        Args:
            device_filter: Function that returns True if port name matches desired device
            poll_interval: How often to check for device changes (seconds)
            port_selector: Optional function to select best port from candidates.
                          If None, selects first matching port.
        """
        self._input_manager = MidiInputManager(device_filter, poll_interval, port_selector)
        self._output_manager = MidiOutputManager(device_filter, poll_interval, port_selector)

    def on_message(self, callback: Callable[[mido.Message], None]) -> None:
        """
        Register callback for incoming MIDI messages.

        Callback is executed in mido's internal I/O thread - keep it fast!

        Args:
            callback: Function that receives mido.Message
        """
        self._input_manager.on_message(callback)

    def on_connection_changed(self, callback: Callable[[bool, Optional[str]], None]) -> None:
        """
        Register callback for connection state changes.

        Callback is executed when device connects or disconnects.

        Args:
            callback: Function that receives (is_connected: bool, port_name: Optional[str])
        """
        # Register same callback for both input and output (fires twice, but that's ok)
        self._input_manager.on_connection_changed(callback)
        self._output_manager.on_connection_changed(callback)

    def send(self, message: mido.Message) -> bool:
        """
        Send MIDI message to device.

        Args:
            message: MIDI message to send

        Returns:
            True if sent successfully, False if not connected
        """
        return self._output_manager.send(message)

    def start(self) -> None:
        """Start monitoring for MIDI devices."""
        self._input_manager.start()
        self._output_manager.start()
        logger.debug("MidiManager started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self._input_manager.stop()
        self._output_manager.stop()
        logger.debug("MidiManager stopped")

    @property
    def is_connected(self) -> bool:
        """Check if both input and output devices are connected."""
        return self._input_manager.is_connected and self._output_manager.is_connected

    @property
    def current_input_port(self) -> Optional[str]:
        """Get currently connected input port name."""
        return self._input_manager.current_port

    @property
    def current_output_port(self) -> Optional[str]:
        """Get currently connected output port name."""
        return self._output_manager.current_port

    @staticmethod
    def list_ports() -> dict:
        """
        List all available MIDI ports.

        Returns:
            Dictionary with 'input' and 'output' lists of port names
        """
        return {
            'input': mido.get_input_names(),
            'output': mido.get_output_names()
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
