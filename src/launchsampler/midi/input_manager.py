"""Generic MIDI input manager with hot-plug support."""

import logging
import threading
import time
from typing import Callable, Optional

import mido

logger = logging.getLogger(__name__)


class MidiInputManager:
    """
    Generic MIDI input manager with hot-plug support.

    Monitors for MIDI input devices matching a filter function,
    automatically connects/reconnects when devices are plugged/unplugged.
    """

    def __init__(
        self,
        device_filter: Callable[[str], bool],
        poll_interval: float = 5.0,
        port_selector: Optional[Callable[[list[str]], Optional[str]]] = None
    ):
        """
        Initialize MIDI input manager.

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
        self._port: Optional[mido.ports.BaseInput] = None
        self._port_lock = threading.Lock()
        self._message_callback: Optional[Callable[[mido.Message], None]] = None
        self._no_device_warned = False

    def on_message(self, callback: Callable[[mido.Message], None]) -> None:
        """
        Register callback for incoming MIDI messages.

        Callback is executed in mido's internal I/O thread - keep it fast!

        Args:
            callback: Function that receives mido.Message
        """
        self._message_callback = callback

    def start(self) -> None:
        """Start monitoring for MIDI input devices."""
        if self._running:
            logger.warning("MidiInputManager is already running")
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self._monitor_thread.start()
        logger.debug("MidiInputManager started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self._running = False

        with self._port_lock:
            if self._port:
                try:
                    self._port.close()
                except Exception as e:
                    logger.error(f"Error closing MIDI input port: {e}")
                self._port = None

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

        logger.debug("MidiInputManager stopped")

    def _find_matching_port(self) -> Optional[str]:
        """Find first available port matching the device filter."""
        available_ports = mido.get_input_names()
        matching_ports = [p for p in available_ports if self._device_filter(p)]

        if not matching_ports:
            return None

        # Use custom selector if provided, otherwise take first match
        if self._port_selector:
            return self._port_selector(matching_ports)

        return matching_ports[0]

    def _monitor_devices(self) -> None:
        """Monitor for device connection/disconnection."""
        logger.debug("Starting MIDI input device monitoring")
        last_available_ports = set()

        while self._running:
            try:
                available_ports = set(mido.get_input_names())

                # Log newly connected/disconnected ports
                new_ports = available_ports - last_available_ports
                removed_ports = last_available_ports - available_ports

                for port in new_ports:
                    logger.info(f"MIDI port connected: {port}")

                for port in removed_ports:
                    logger.info(f"MIDI port disconnected: {port}")

                last_available_ports = available_ports

                with self._port_lock:
                    # If we have a port but it's no longer available
                    if self._port and self._port.name not in available_ports:
                        logger.warning(f"MIDI input disconnected: {self._port.name}")
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
                            logger.info(f"MIDI input detected: {port}")
                            self._connect_to_port(port)
                        else:
                            if not self._no_device_warned:
                                logger.warning("No matching MIDI input device found")
                                self._no_device_warned = True

                time.sleep(self._poll_interval)

            except Exception as e:
                logger.error(f"Error in MIDI input monitoring: {e}")
                time.sleep(self._poll_interval)

    def _connect_to_port(self, port_name: str) -> None:
        """
        Connect to a MIDI input port.

        Note: Should be called with _port_lock held.
        """
        try:
            self._port = mido.open_input(port_name, callback=self._midi_callback)
            logger.info(f"Connected to MIDI input: {port_name}")
        except Exception as e:
            logger.error(f"Failed to connect to {port_name}: {e}")
            self._port = None

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

    @property
    def is_connected(self) -> bool:
        """Check if MIDI input device is currently connected."""
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
