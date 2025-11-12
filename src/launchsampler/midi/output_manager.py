"""Generic MIDI output manager with hot-plug support."""

import logging
import threading
import time
from typing import Callable, Optional

import mido

logger = logging.getLogger(__name__)


class MidiOutputManager:
    """
    Generic MIDI output manager with hot-plug support.

    Monitors for MIDI output devices matching a filter function,
    automatically connects/reconnects when devices are plugged/unplugged.
    """

    def __init__(
        self,
        device_filter: Callable[[str], bool],
        poll_interval: float = 5.0,
        port_selector: Optional[Callable[[list[str]], Optional[str]]] = None
    ):
        """
        Initialize MIDI output manager.

        Args:
            device_filter: Function that returns True if port name matches desired device
            poll_interval: How often to check for device changes (seconds)
            port_selector: Optional function to select best port from candidates.
                          If None, selects first matching port.
        """
        self._device_filter = device_filter
        self._poll_interval = poll_interval
        self._port_selector = port_selector
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._port: Optional[mido.ports.BaseOutput] = None
        self._port_lock = threading.Lock()
        self._no_device_warned = False

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

    def start(self) -> None:
        """Start monitoring for MIDI output devices."""
        if self._running:
            logger.warning("MidiOutputManager is already running")
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self._monitor_thread.start()
        logger.debug("MidiOutputManager started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self._running = False

        with self._port_lock:
            if self._port:
                try:
                    self._port.close()
                except Exception as e:
                    logger.error(f"Error closing MIDI output port: {e}")
                self._port = None

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

        logger.debug("MidiOutputManager stopped")

    def _find_matching_port(self) -> Optional[str]:
        """Find first available port matching the device filter."""
        available_ports = mido.get_output_names()
        matching_ports = [p for p in available_ports if self._device_filter(p)]

        if not matching_ports:
            return None

        # Use custom selector if provided, otherwise take first match
        if self._port_selector:
            return self._port_selector(matching_ports)

        return matching_ports[0]

    def _monitor_devices(self) -> None:
        """Monitor for device connection/disconnection."""
        logger.debug("Starting MIDI output device monitoring")
        last_available_ports = set()

        while self._running:
            try:
                available_ports = set(mido.get_output_names())

                # Log changes (but less verbose than input manager)
                new_ports = available_ports - last_available_ports
                removed_ports = last_available_ports - available_ports

                for port in new_ports:
                    logger.debug(f"MIDI output port connected: {port}")

                for port in removed_ports:
                    logger.debug(f"MIDI output port disconnected: {port}")

                last_available_ports = available_ports

                with self._port_lock:
                    # If we have a port but it's no longer available
                    if self._port and self._port.name not in available_ports:
                        logger.warning(f"MIDI output disconnected: {self._port.name}")
                        try:
                            self._port.close()
                        except Exception:
                            pass
                        self._port = None
                        self._no_device_warned = False

                    # If we don't have a port, try to find one
                    if not self._port:
                        port = self._find_matching_port()
                        if port:
                            logger.info(f"MIDI output detected: {port}")
                            self._connect_to_port(port)
                        else:
                            if not self._no_device_warned:
                                logger.debug("No matching MIDI output device found")
                                self._no_device_warned = True

                time.sleep(self._poll_interval)

            except Exception as e:
                logger.error(f"Error in MIDI output monitoring: {e}")
                time.sleep(self._poll_interval)

    def _connect_to_port(self, port_name: str) -> None:
        """
        Connect to a MIDI output port.

        Note: Should be called with _port_lock held.
        """
        try:
            self._port = mido.open_output(port_name)
            logger.info(f"Connected to MIDI output: {port_name}")
        except Exception as e:
            logger.error(f"Failed to connect to {port_name}: {e}")
            self._port = None

    @property
    def is_connected(self) -> bool:
        """Check if MIDI output device is currently connected."""
        with self._port_lock:
            return self._port is not None

    @property
    def current_port(self) -> Optional[str]:
        """Get currently connected port name."""
        with self._port_lock:
            return self._port.name if self._port else None

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
