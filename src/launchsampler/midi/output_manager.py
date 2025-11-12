"""Generic MIDI output manager with hot-plug support."""

import logging
from typing import Callable, Optional

import mido

from .base_manager import BaseMidiManager

logger = logging.getLogger(__name__)


class MidiOutputManager(BaseMidiManager[mido.ports.BaseOutput]):
    """
    Generic MIDI output manager with hot-plug support.

    Monitors for MIDI output devices matching a filter function,
    automatically connects/reconnects when devices are plugged/unplugged.
    """

    def send(self, message: mido.Message) -> bool:
        """
        Send MIDI message to device.

        Args:
            message: MIDI message to send

        Returns:
            True if sent successfully, False if not connected
        """
        with self._port_lock:
            if self._port:
                try:
                    self._port.send(message)
                    return True
                except Exception as e:
                    logger.error(f"Error sending MIDI message: {e}")
                    return False
            return False

    def _get_available_ports(self) -> list[str]:
        """Get list of available MIDI output ports."""
        return mido.get_output_names()

    def _open_port(self, port_name: str) -> mido.ports.BaseOutput:
        """
        Open a MIDI output port.

        Args:
            port_name: Name of the port to open

        Returns:
            Opened MIDI output port

        Raises:
            Exception: If port cannot be opened
        """
        return mido.open_output(port_name)

    def _get_port_type_name(self) -> str:
        """Get port type name for logging."""
        return "output"

    def _get_log_level_for_port_changes(self) -> int:
        """Get logging level for port connection/disconnection events."""
        return logging.INFO
