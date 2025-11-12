"""Launchpad MIDI controller with hot-plug support."""

import logging
import threading
import time
from typing import Callable, Optional

import mido

logger = logging.getLogger(__name__)


class LaunchpadController:
    """
    MIDI controller for Launchpad devices with hot-plug support.

    Automatically detects and connects to Launchpad devices,
    handles reconnection when devices are plugged/unplugged.
    """

    # Launchpad device name patterns to detect
    LAUNCHPAD_PATTERNS = [
        "Launchpad X",
        "Launchpad Mini",
        "Launchpad Pro",
        "LPProMK3",  # Launchpad Pro MK3
        "LPMiniMK3",  # Launchpad Mini MK3
        "LPX",  # Launchpad X
        "Launchpad",
    ]

    def __init__(self, poll_interval: float = 5.0):
        """
        Initialize the Launchpad controller.

        Args:
            poll_interval: How often to check for new/removed devices (seconds)
        """
        self.poll_interval = poll_interval
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.inport: Optional[mido.ports.BaseInput] = None

        # Event callbacks
        self._on_pad_pressed: Optional[Callable[[int], None]] = None
        self._on_pad_released: Optional[Callable[[int], None]] = None

        # Thread lock for port access (shared between monitor thread and main thread)
        self._port_lock = threading.Lock()

    def on_pad_pressed(self, callback: Callable[[int], None]) -> None:
        """
        Register callback for pad press events.

        Callback is executed in mido's internal I/O thread - keep it fast!

        Args:
            callback: Function that takes pad_index (0-63) as argument
        """
        self._on_pad_pressed = callback

    def on_pad_released(self, callback: Callable[[int], None]) -> None:
        """
        Register callback for pad release events.

        Callback is executed in mido's internal I/O thread - keep it fast!

        Args:
            callback: Function that takes pad_index (0-63) as argument
        """
        self._on_pad_released = callback

    def start(self) -> None:
        """Start monitoring for Launchpad devices."""
        if self.running:
            logger.warning("LaunchpadController is already running")
            return

        self.running = True

        # Start device detection thread
        self.monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self.monitor_thread.start()

        logger.info("LaunchpadController started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self.running = False

        # Close current port
        with self._port_lock:
            if self.inport:
                try:
                    self.inport.close()
                except Exception as e:
                    logger.error(f"Error closing MIDI port: {e}")
                self.inport = None

        # Wait for threads to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

        logger.info("LaunchpadController stopped")

    def _is_launchpad_port(self, port_name: str) -> bool:
        """Check if port name matches a Launchpad device."""
        return any(pattern in port_name for pattern in self.LAUNCHPAD_PATTERNS)

    def _find_launchpad_port(self) -> Optional[str]:
        """
        Find first available Launchpad port.

        Prefers "MIDI 1" ports for devices with multiple MIDI ports.
        """
        available_ports = mido.get_input_names()
        launchpad_ports = [p for p in available_ports if self._is_launchpad_port(p)]

        if not launchpad_ports:
            return None

        # Prefer ports with "MIDI 1" in the name (e.g., "LPProMK3 MIDI 1")
        midi1_ports = [p for p in launchpad_ports if "MIDI 1" in p]
        if midi1_ports:
            return midi1_ports[0]

        # Otherwise return first Launchpad port found
        return launchpad_ports[0]

    def _monitor_devices(self) -> None:
        """Monitor for Launchpad device connection/disconnection."""
        logger.info("Starting device monitoring")
        last_available_ports = set()

        while self.running:
            try:
                # Check if current port is still available
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
                    if self.inport and self.inport.name not in available_ports:
                        logger.warning(f"Launchpad disconnected: {self.inport.name}")
                        try:
                            self.inport.close()
                        except Exception:
                            pass
                        self.inport = None
                        # Reset warning flag so we can warn again
                        if hasattr(self, '_no_device_warned'):
                            delattr(self, '_no_device_warned')

                    # If we don't have a port, try to find one
                    if not self.inport:
                        port = self._find_launchpad_port()
                        if port:
                            logger.info(f"Launchpad detected: {port}")
                            self._connect_to_port(port)
                        else:
                            # Only log warning once, not every poll
                            if not hasattr(self, '_no_device_warned'):
                                logger.warning("No Launchpad device found. Audio will work without MIDI control.")
                                self._no_device_warned = True

                # Wait before next check
                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in device monitoring: {e}")
                time.sleep(self.poll_interval)

    def _connect_to_port(self, port_name: str) -> None:
        """
        Connect to a MIDI port using callback-based approach.

        Note: Should be called with _port_lock held.
        """
        try:
            # Open port with callback for immediate message processing
            self.inport = mido.open_input(port_name, callback=self._midi_callback)
            logger.info(f"Connected to {port_name}")

        except Exception as e:
            logger.error(f"Failed to connect to {port_name}: {e}")
            self.inport = None

    def _midi_callback(self, msg: mido.Message) -> None:
        """
        MIDI message callback - called from mido's internal I/O thread.

        This is invoked by mido's own thread (not one we create) when MIDI
        messages arrive, providing the lowest possible latency.
        """
        try:
            # Filter out clock messages
            if msg.type == 'clock':
                return

            # Handle note on/off
            if msg.type == 'note_on':
                # Note on with velocity 0 is actually note off
                if msg.velocity > 0:
                    self._handle_note_on(msg.note)
                else:
                    self._handle_note_off(msg.note)
            elif msg.type == 'note_off':
                self._handle_note_off(msg.note)

        except Exception as e:
            logger.error(f"Error in MIDI callback: {e}")

    def _handle_note_on(self, note: int) -> None:
        """
        Handle note on (pad pressed) event.

        Called from mido's internal I/O thread.
        """
        # Convert MIDI note to pad index (0-63)
        # Launchpad uses notes 0-63 for the 8x8 grid
        if 0 <= note < 64:
            logger.debug(f"Pad pressed: {note}")
            if self._on_pad_pressed:
                self._on_pad_pressed(note)

    def _handle_note_off(self, note: int) -> None:
        """
        Handle note off (pad released) event.

        Called from mido's internal I/O thread.
        """
        if 0 <= note < 64:
            logger.debug(f"Pad released: {note}")
            if self._on_pad_released:
                self._on_pad_released(note)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
