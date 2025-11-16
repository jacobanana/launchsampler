"""Launchpad controller."""

import logging
from typing import Optional

import mido

from launchsampler.midi import MidiManager
from launchsampler.models import Color
from launchsampler.protocols import MidiEvent, MidiObserver
from launchsampler.devices.protocols import PadPressEvent, PadReleaseEvent, ControlChangeEvent
from launchsampler.utils import ObserverManager
from .device import LaunchpadDevice

logger = logging.getLogger(__name__)


class LaunchpadController:
    """
    High-level Launchpad controller.

    Composes MidiManager with Launchpad device protocol to provide
    a clean, user-facing API for Launchpad control.
    """

    def __init__(self, poll_interval: float = 5.0):
        """
        Initialize Launchpad controller.

        Args:
            poll_interval: How often to check for device changes (seconds)
        """
        # Use generic MidiManager with Launchpad device filter and port selector
        self._midi = MidiManager(
            device_filter=LaunchpadDevice.matches,
            poll_interval=poll_interval,
            port_selector=LaunchpadDevice.select_port
        )
        self._midi.on_message(self._handle_message)
        self._midi.on_connection_changed(self._handle_connection_changed)

        # Observer pattern for MIDI events
        self._observers = ObserverManager[MidiObserver](observer_type_name="MIDI")

        # Launchpad device instance (created when connected)
        self._device: Optional[LaunchpadDevice] = None

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
        """Start monitoring for Launchpad devices."""
        self._midi.start()
        logger.info("LaunchpadController started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        # Shutdown device output (exit programmer mode) before stopping MIDI
        if self._device:
            try:
                self._device.output.shutdown()
                logger.info("Launchpad device shut down")
            except Exception as e:
                logger.error(f"Error shutting down Launchpad device: {e}")
            self._device = None

        self._midi.stop()
        logger.info("LaunchpadController stopped")

    def _handle_message(self, msg: mido.Message) -> None:
        """
        Handle incoming MIDI message using Launchpad protocol.

        Called from mido's internal I/O thread.
        """
        try:
            # Use device input if available, otherwise use deprecated static method
            if self._device:
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
            else:
                # Fallback to old static method for backward compatibility
                result = LaunchpadDevice.parse_input(msg)
                if result:
                    event_type, pad_index = result
                    if event_type == "pad_press":
                        logger.info(f"Pad pressed: {pad_index} (fallback)")
                        self._notify_observers(MidiEvent.NOTE_ON, pad_index)
                    elif event_type == "pad_release":
                        logger.info(f"Pad released: {pad_index} (fallback)")
                        self._notify_observers(MidiEvent.NOTE_OFF, pad_index)

        except Exception as e:
            logger.error(f"Error handling Launchpad message: {e}")

    def _handle_connection_changed(self, is_connected: bool, port_name: Optional[str]) -> None:
        """Handle MIDI connection state changes."""
        if is_connected and port_name:
            try:
                self._device = LaunchpadDevice(self._midi, port_name)
                self._device.output.initialize()
                logger.info(f"Launchpad device initialized: {self._device.info.model.display_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Launchpad device: {e}")
                self._device = None
        else:
            if self._device:
                try:
                    self._device.output.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down Launchpad device: {e}")
                self._device = None

        event = MidiEvent.CONTROLLER_CONNECTED if is_connected else MidiEvent.CONTROLLER_DISCONNECTED
        self._notify_observers(event, -1)  # -1 indicates no specific pad
        logger.info(f"MIDI controller {'connected' if is_connected else 'disconnected'}: {port_name}")

    @property
    def is_connected(self) -> bool:
        """Check if Launchpad device is connected."""
        return self._midi.is_connected

    @property
    def device_name(self) -> str:
        """Get the name of the connected Launchpad device."""
        if self._midi.is_connected and self._midi.current_input_port:
            # Extract device name from port name (e.g., "Launchpad MK2:Launchpad MK2 MIDI 1 28:0")
            port_name = self._midi.current_input_port
            # Take the first part before the colon
            device_name = port_name.split(':')[0] if ':' in port_name else port_name
            return device_name
        return "No Device"

    @property
    def num_pads(self) -> int:
        """Get number of pads on this Launchpad device."""
        return LaunchpadDevice.NUM_PADS

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
