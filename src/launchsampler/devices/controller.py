"""Generic device controller for grid-based MIDI controllers."""

import logging
from typing import Optional

import mido

from launchsampler.midi import MidiManager
from launchsampler.models import Color
from launchsampler.protocols import MidiEvent, MidiObserver
from launchsampler.devices.protocols import PadPressEvent, PadReleaseEvent, ControlChangeEvent
from launchsampler.devices.registry import get_registry
from launchsampler.devices.device import GenericDevice
from launchsampler.devices.config import DeviceConfig
from launchsampler.utils import ObserverManager

logger = logging.getLogger(__name__)


class DeviceController:
    """
    High-level controller for grid-based MIDI devices.

    Composes MidiManager with device registry to provide a clean,
    user-facing API for controlling any supported grid device
    (Launchpad, APC, etc.).

    The controller automatically detects connected devices using the
    registry and provides a unified API regardless of the specific
    hardware model.
    """

    def __init__(self, poll_interval: float = 5.0):
        """
        Initialize device controller.

        Args:
            poll_interval: How often to check for device changes (seconds)
        """
        # Get device registry
        self._registry = get_registry()

        # Detected device config (set when device is detected)
        self._detected_config: Optional[DeviceConfig] = None

        # Use generic MidiManager with config-driven device filter and port selectors
        self._midi = MidiManager(
            device_filter=self._device_filter,
            poll_interval=poll_interval,
            input_port_selector=self._select_input_port,
            output_port_selector=self._select_output_port
        )
        self._midi.on_message(self._handle_message)
        self._midi.on_connection_changed(self._handle_connection_changed)

        # Observer pattern for MIDI events
        self._observers = ObserverManager[MidiObserver](observer_type_name="MIDI")

        # Device instance (created when connected)
        self._device: Optional[GenericDevice] = None

    def _device_filter(self, port_name: str) -> bool:
        """Filter function for MidiManager - detect if port matches any supported device."""
        config = self._registry.detect_device(port_name)
        if config:
            # Cache detected config for port selection
            self._detected_config = config
            return True
        return False

    def _select_input_port(self, matching_ports: list[str]) -> Optional[str]:
        """Select best input port using detected config."""
        if self._detected_config is None:
            return matching_ports[0] if matching_ports else None
        return self._detected_config.select_input_port(matching_ports)

    def _select_output_port(self, matching_ports: list[str]) -> Optional[str]:
        """Select best output port using detected config."""
        if self._detected_config is None:
            return matching_ports[0] if matching_ports else None
        return self._detected_config.select_output_port(matching_ports)

    def register_observer(self, observer: MidiObserver) -> None:
        """Register observer for MIDI events."""
        self._observers.register(observer)

    def unregister_observer(self, observer: MidiObserver) -> None:
        """Unregister observer."""
        self._observers.unregister(observer)

    def _notify_observers(self, event: MidiEvent, pad_index: int, control: int = 0, value: int = 0) -> None:
        """
        Notify all observers of a MIDI event.

        Args:
            event: The MIDI event type
            pad_index: Pad index (0-63) or -1 for non-pad events
            control: MIDI CC control number (for CONTROL_CHANGE events)
            value: MIDI CC value (for CONTROL_CHANGE events)
        """
        self._observers.notify('on_midi_event', event, pad_index, control, value)

    def set_pad_color(self, pad_index: int, color: Color) -> bool:
        """
        Set LED color for a pad (RGB mode).

        Args:
            pad_index: Pad 0-63
            color: RGB color

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set pad color: No device connected")
            return False

        try:
            self._device.output.set_led(pad_index, color)
            return True
        except Exception as e:
            logger.error(f"Error setting pad color: {e}")
            return False

    def set_pad_flashing(self, pad_index: int, color: int) -> bool:
        """
        Set LED to flash using palette color.

        Args:
            pad_index: Pad 0-63
            color: Palette color index (0-127)

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set pad flashing: No device connected")
            return False

        try:
            self._device.output.set_led_flashing(pad_index, color)
            return True
        except Exception as e:
            logger.error(f"Error setting pad flashing: {e}")
            return False

    def set_pad_pulsing(self, pad_index: int, color: int) -> bool:
        """
        Set LED to pulse using palette color.

        Args:
            pad_index: Pad 0-63
            color: Palette color index (0-127)

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set pad pulsing: No device connected")
            return False

        try:
            self._device.output.set_led_pulsing(pad_index, color)
            return True
        except Exception as e:
            logger.error(f"Error setting pad pulsing: {e}")
            return False

    def set_pad_static(self, pad_index: int, color: int) -> bool:
        """
        Set LED to static palette color.

        Args:
            pad_index: Pad 0-63
            color: Palette color index (0-127)

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set pad static: No device connected")
            return False

        try:
            self._device.output.set_led_static(pad_index, color)
            return True
        except Exception as e:
            logger.error(f"Error setting pad static: {e}")
            return False

    def set_leds_bulk(self, updates: list[tuple[int, Color]]) -> bool:
        """
        Bulk update multiple LED colors (more efficient than individual updates).

        Args:
            updates: List of (pad_index, color) tuples

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set LEDs bulk: No device connected")
            return False

        try:
            self._device.output.set_leds_bulk(updates)
            return True
        except Exception as e:
            logger.error(f"Error setting LEDs bulk: {e}")
            return False

    def start(self) -> None:
        """Start monitoring for supported MIDI devices."""
        self._midi.start()
        logger.info("DeviceController started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        # Shutdown device output (exit programmer mode) before stopping MIDI
        if self._device:
            try:
                self._device.output.shutdown()
                logger.info("Device shut down")
            except Exception as e:
                logger.error(f"Error shutting down device: {e}")
            self._device = None

        self._midi.stop()
        logger.info("DeviceController stopped")

    def _handle_message(self, msg: mido.Message) -> None:
        """
        Handle incoming MIDI message using device-specific protocol.

        Called from mido's internal I/O thread.
        """
        try:
            if not self._device:
                logger.warning("Received message but no device is connected")
                return

            event = self._device.input.parse_message(msg)
            if event:
                if isinstance(event, PadPressEvent):
                    logger.info(f"Pad pressed: {event.pad_index} (note {msg.note})")
                    self._notify_observers(MidiEvent.NOTE_ON, event.pad_index)

                elif isinstance(event, PadReleaseEvent):
                    logger.info(f"Pad released: {event.pad_index} (note {msg.note})")
                    self._notify_observers(MidiEvent.NOTE_OFF, event.pad_index)

                elif isinstance(event, ControlChangeEvent):
                    logger.info(f"Control change: control={event.control}, value={event.value}")
                    self._notify_observers(MidiEvent.CONTROL_CHANGE, -1, event.control, event.value)
            else:
                logger.debug(f"Unhandled message: {msg}")

        except Exception as e:
            logger.error(f"Error handling MIDI message: {e}")

    def _handle_connection_changed(self, is_connected: bool, port_name: Optional[str]) -> None:
        """Handle MIDI connection state changes."""
        if is_connected and port_name:
            try:
                # Detect device config from port name
                config = self._registry.detect_device(port_name)
                if config is None:
                    logger.error(f"No device config found for port: {port_name}")
                    return

                # Create device from config
                self._device = self._registry.create_device(config, self._midi)
                self._device.output.initialize()
                logger.info(f"Device initialized: {self._device.display_name}")
            except Exception as e:
                logger.error(f"Failed to initialize device: {e}")
                self._device = None
        else:
            if self._device:
                try:
                    self._device.output.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down device: {e}")
                self._device = None

        event = MidiEvent.CONTROLLER_CONNECTED if is_connected else MidiEvent.CONTROLLER_DISCONNECTED
        self._notify_observers(event, -1)  # -1 indicates no specific pad
        logger.info(f"MIDI controller {'connected' if is_connected else 'disconnected'}: {port_name}")

    @property
    def is_connected(self) -> bool:
        """Check if a device is connected."""
        return self._midi.is_connected

    @property
    def device_name(self) -> str:
        """Get the model name of the connected device."""
        if self._device:
            return self._device.config.model
        return "No Device"

    @property
    def num_pads(self) -> int:
        """Get number of pads on this device."""
        if self._device:
            return self._device.num_pads
        return 64  # Default

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
