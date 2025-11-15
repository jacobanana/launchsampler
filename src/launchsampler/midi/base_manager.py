"""Base MIDI manager with hot-plug support."""

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Generic, Optional, TypeVar

import mido

logger = logging.getLogger(__name__)

# Type variable for port types (BaseInput or BaseOutput)
PortType = TypeVar('PortType', bound=mido.ports.BaseIOPort)


class BaseMidiManager(ABC, Generic[PortType]):
    """
    Base MIDI manager with hot-plug support.

    Monitors for MIDI devices matching a filter function,
    automatically connects/reconnects when devices are plugged/unplugged.

    Subclasses must implement abstract methods for port-specific operations.
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
        self._device_filter = device_filter
        self._poll_interval = poll_interval
        self._port_selector = port_selector
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._port: Optional[PortType] = None
        self._port_lock = threading.Lock()
        self._no_device_warned = False
        self._on_connection_changed: Optional[Callable[[bool, Optional[str]], None]] = None

    @abstractmethod
    def _get_available_ports(self) -> list[str]:
        """
        Get list of available ports.

        Returns:
            List of available port names
        """
        pass

    @abstractmethod
    def _open_port(self, port_name: str) -> PortType:
        """
        Open a MIDI port.

        Args:
            port_name: Name of the port to open

        Returns:
            Opened port object

        Raises:
            Exception: If port cannot be opened
        """
        pass

    @abstractmethod
    def _get_port_type_name(self) -> str:
        """
        Get human-readable port type name for logging.

        Returns:
            "input" or "output"
        """
        pass

    @abstractmethod
    def _get_log_level_for_port_changes(self) -> int:
        """
        Get logging level for port connection/disconnection events.

        Returns:
            logging level constant (e.g., logging.INFO, logging.DEBUG)
        """
        pass

    def start(self) -> None:
        """Start monitoring for MIDI devices."""
        if self._running:
            logger.warning(f"Midi{self._get_port_type_name().capitalize()}Manager is already running")
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self._monitor_thread.start()
        logger.debug(f"Midi{self._get_port_type_name().capitalize()}Manager started")

    def on_connection_changed(self, callback: Callable[[bool, Optional[str]], None]) -> None:
        """
        Register callback for connection state changes.

        Args:
            callback: Function that receives (is_connected: bool, port_name: Optional[str])
        """
        self._on_connection_changed = callback

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self._running = False

        with self._port_lock:
            if self._port:
                try:
                    self._port.close()
                except Exception as e:
                    logger.error(f"Error closing MIDI {self._get_port_type_name()} port: {e}")
                self._port = None

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

        logger.debug(f"Midi{self._get_port_type_name().capitalize()}Manager stopped")

    def _find_matching_port(self) -> Optional[str]:
        """Find first available port matching the device filter."""
        available_ports = self._get_available_ports()
        matching_ports = [p for p in available_ports if self._device_filter(p)]

        if not matching_ports:
            return None

        # Use custom selector if provided, otherwise take first match
        if self._port_selector:
            return self._port_selector(matching_ports)

        return matching_ports[0]

    def _monitor_devices(self) -> None:
        """Monitor for device connection/disconnection."""
        port_type = self._get_port_type_name()
        log_level = self._get_log_level_for_port_changes()

        logger.debug(f"Starting MIDI {port_type} device monitoring")
        last_available_ports = set()

        while self._running:
            try:
                available_ports = set(self._get_available_ports())

                # Log newly connected/disconnected ports
                new_ports = available_ports - last_available_ports
                removed_ports = last_available_ports - available_ports

                for port in new_ports:
                    logger.log(log_level, f"MIDI {port_type} port connected: {port}")

                for port in removed_ports:
                    logger.log(log_level, f"MIDI {port_type} port disconnected: {port}")

                last_available_ports = available_ports

                with self._port_lock:
                    # If we have a port but it's no longer available
                    if self._port and self._port.name not in available_ports:
                        port_name = self._port.name
                        logger.warning(f"MIDI {port_type} disconnected: {port_name}")
                        try:
                            self._port.close()
                        except Exception:
                            pass
                        self._port = None
                        self._no_device_warned = False
                        # Fire callback in a separate thread to avoid blocking/deadlock
                        if self._on_connection_changed:
                            def fire_callback():
                                try:
                                    self._on_connection_changed(False, None)
                                except Exception as e:
                                    logger.error(f"Error in connection callback: {e}")
                            threading.Thread(target=fire_callback, daemon=True).start()

                    # If we don't have a port, try to find one
                    if not self._port:
                        port = self._find_matching_port()
                        if port:
                            logger.info(f"MIDI {port_type} detected: {port}")
                            self._connect_to_port(port)
                        else:
                            if not self._no_device_warned:
                                warning_log_level = logging.DEBUG if log_level == logging.DEBUG else logging.WARNING
                                logger.log(warning_log_level, f"No matching MIDI {port_type} device found")
                                self._no_device_warned = True

                time.sleep(self._poll_interval)

            except Exception as e:
                logger.error(f"Error in MIDI {port_type} monitoring: {e}")
                time.sleep(self._poll_interval)

    def _connect_to_port(self, port_name: str) -> None:
        """
        Connect to a MIDI port.

        Note: Should be called with _port_lock held.
        """
        port_type = self._get_port_type_name()
        try:
            self._port = self._open_port(port_name)
            logger.info(f"Connected to MIDI {port_type}: {port_name}")
            # Fire callback in a separate thread to avoid blocking/deadlock
            if self._on_connection_changed:
                def fire_callback():
                    try:
                        self._on_connection_changed(True, port_name)
                    except Exception as e:
                        logger.error(f"Error in connection callback: {e}")
                threading.Thread(target=fire_callback, daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to connect to {port_name}: {e}")
            self._port = None

    @property
    def is_connected(self) -> bool:
        """Check if MIDI device is currently connected."""
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
