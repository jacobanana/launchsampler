"""
Generic device controller for grid-based MIDI controllers.

Architecture Overview
=====================

The DeviceController is the main user-facing API for interacting with MIDI grid
controllers. It sits at the top of the device architecture and hides all hardware
complexity from the application.

Connection Flow
---------------

::

    ┌─────────────────────────────────────────────────────────────────────┐
    │                         USER APPLICATION                            │
    │                    (Your Sampler Software)                          │
    └────────────────────────────┬────────────────────────────────────────┘
                                 │
                        Uses high-level API
                                 ↓
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    DeviceController                                 │
    │                  (devices/controller.py)                            │
    │                                                                     │
    │  🎮 What it does:                                                   │
    │    - Manages connection to the device                              │
    │    - Provides user-friendly methods (set_pad_color, etc.)          │
    │    - Handles observers (notify when buttons pressed)               │
    │    - Hides all the complexity below                                │
    └──────────┬─────────────────┬────────────────────────┬───────────────┘
               │                 │                        │
        Asks for help    Detects devices         Sends messages
               ↓                 ↓                        ↓
       ┌───────────────┐ ┌──────────────┐      ┌─────────────────┐
       │ DeviceRegistry│ │ MidiManager  │      │  MidiManager    │
       │ (registry.py) │ │ (generic)    │      │  (output)       │
       └───────┬───────┘ └──────────────┘      └─────────────────┘
               │
        Loads config &
        creates device
               ↓
    ┌──────────────────────────────────────────────────────────────────────┐
    │                        GenericDevice                                 │
    │                         (device.py)                                  │
    │                                                                      │
    │  Two sides:                                                          │
    │    - Input: MIDI messages → Events (button presses)                 │
    │    - Output: Commands → MIDI messages (LED control)                 │
    └──────────────────────────────────────────────────────────────────────┘

Key Design Principle
--------------------

The DeviceController knows NOTHING about:
- MIDI note numbers
- SysEx messages
- Hardware-specific quirks

It only deals with logical pad indices (0-63) and abstract colors.
All hardware translation happens in the layers below.

Usage Example
-------------

.. code-block:: python

    controller = DeviceController()
    controller.start()
    controller.set_pad_color(21, Color(255, 0, 0))  # Works with ANY device!
"""

import logging
from typing import TYPE_CHECKING

import mido

from launchsampler.devices.protocols import ControlChangeEvent, PadPressEvent, PadReleaseEvent
from launchsampler.devices.registry import DeviceRegistry
from launchsampler.midi import MidiManager
from launchsampler.model_manager import ObserverManager
from launchsampler.models import Color
from launchsampler.protocols import MidiEvent, MidiObserver

if TYPE_CHECKING:
    from launchsampler.devices.config import DeviceConfig
    from launchsampler.devices.device import GenericDevice

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

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def __init__(self, poll_interval: float = 5.0):
        """
        Initialize device controller.

        Args:
            poll_interval: How often to check for device changes (seconds)
        """
        # Create device registry
        self._registry = DeviceRegistry()

        # Detected device config (set when device is detected)
        self._detected_config: DeviceConfig | None = None

        # Use generic MidiManager with config-driven device filter and port selectors
        self._midi = MidiManager(
            device_filter=self._device_filter,
            poll_interval=poll_interval,
            input_port_selector=self._select_input_port,
            output_port_selector=self._select_output_port,
        )
        self._midi.on_message(self._handle_message)
        self._midi.on_connection_changed(self._handle_connection_changed)

        # Observer pattern for MIDI events
        self._observers = ObserverManager[MidiObserver](observer_type_name="MIDI")

        # Device instance (created when connected)
        self._device: GenericDevice | None = None

    # ================================================================
    # LIFECYCLE MANAGEMENT
    # ================================================================

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

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()

    # ================================================================
    # DEVICE DETECTION & PORT SELECTION
    # ================================================================

    def _device_filter(self, port_name: str) -> bool:
        """Filter function for MidiManager - detect if port matches any supported device."""
        config = self._registry.detect_device(port_name)
        if config:
            # Cache detected config for port selection
            self._detected_config = config
            return True
        return False

    def _select_input_port(self, matching_ports: list[str]) -> str | None:
        """Select best input port using detected config."""
        if self._detected_config is None:
            return matching_ports[0] if matching_ports else None
        return self._detected_config.select_input_port(matching_ports)

    def _select_output_port(self, matching_ports: list[str]) -> str | None:
        """Select best output port using detected config."""
        if self._detected_config is None:
            return matching_ports[0] if matching_ports else None
        return self._detected_config.select_output_port(matching_ports)

    # ================================================================
    # OBSERVER PATTERN
    # ================================================================

    def register_observer(self, observer: MidiObserver) -> None:
        """Register observer for MIDI events."""
        self._observers.register(observer)

    def unregister_observer(self, observer: MidiObserver) -> None:
        """Unregister observer."""
        self._observers.unregister(observer)

    def _notify_observers(
        self, event: MidiEvent, pad_index: int, control: int = 0, value: int = 0
    ) -> None:
        """
        Notify all observers of a MIDI event.

        Args:
            event: The MIDI event type
            pad_index: Pad index (0-63) or -1 for non-pad events
            control: MIDI CC control number (for CONTROL_CHANGE events)
            value: MIDI CC value (for CONTROL_CHANGE events)
        """
        self._observers.notify("on_midi_event", event, pad_index, control, value)

    # ================================================================
    # LED CONTROL - RGB MODE
    # ================================================================

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

    def set_pads(self, updates: list[tuple[int, Color]]) -> bool:
        """
        Set multiple LED colors efficiently.

        Args:
            updates: List of (pad_index, color) tuples

        Returns:
            True if sent successfully, False if not connected
        """
        if not self._device:
            logger.warning("Cannot set LEDs: No device connected")
            return False

        try:
            self._device.output.set_leds(updates)
            return True
        except Exception as e:
            logger.error(f"Error setting LEDs: {e}")
            return False

    # ================================================================
    # LED CONTROL - ANIMATIONS
    # ================================================================

    def set_pad_flashing(self, pad_index: int, color: Color) -> bool:
        """
        Set LED to flash/blink animation.

        Args:
            pad_index: Pad 0-63
            color: RGB color object (device converts to palette internally)

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

    def set_pad_pulsing(self, pad_index: int, color: Color) -> bool:
        """
        Set LED to pulse/breathe animation.

        Args:
            pad_index: Pad 0-63
            color: RGB color object (device converts to palette internally)

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

    # ================================================================
    # MIDI EVENT HANDLING
    # ================================================================

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

    def _handle_connection_changed(self, is_connected: bool, port_name: str | None) -> None:
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

        event = (
            MidiEvent.CONTROLLER_CONNECTED if is_connected else MidiEvent.CONTROLLER_DISCONNECTED
        )
        self._notify_observers(event, -1)  # -1 indicates no specific pad
        logger.info(
            f"MIDI controller {'connected' if is_connected else 'disconnected'}: {port_name}"
        )

    # ================================================================
    # PROPERTIES
    # ================================================================

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
