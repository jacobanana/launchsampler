"""Launchpad controller."""

import logging
from typing import Callable, Optional

import mido

from ..midi import MidiManager
from ..models import Color
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

        # Event callbacks
        self._on_pad_pressed: Optional[Callable[[int], None]] = None
        self._on_pad_released: Optional[Callable[[int], None]] = None

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

    def set_pad_color(self, pad_index: int, color: Color) -> bool:
        """
        Set LED color for a pad.

        Args:
            pad_index: Pad 0-63
            color: RGB color

        Returns:
            True if sent successfully, False if not connected
        """
        msg = LaunchpadDevice.create_led_message(pad_index, color)
        return self._midi.send(msg)

    def start(self) -> None:
        """Start monitoring for Launchpad devices."""
        self._midi.start()
        logger.info("LaunchpadController started")

    def stop(self) -> None:
        """Stop monitoring and close connections."""
        self._midi.stop()
        logger.info("LaunchpadController stopped")

    def _handle_message(self, msg: mido.Message) -> None:
        """
        Handle incoming MIDI message using Launchpad protocol.

        Called from mido's internal I/O thread.
        """
        try:
            event = LaunchpadDevice.parse_input(msg)
            if event:
                event_type, pad_index = event

                if event_type == "pad_press":
                    logger.debug(f"Pad pressed: {pad_index}")
                    if self._on_pad_pressed:
                        self._on_pad_pressed(pad_index)

                elif event_type == "pad_release":
                    logger.debug(f"Pad released: {pad_index}")
                    if self._on_pad_released:
                        self._on_pad_released(pad_index)

        except Exception as e:
            logger.error(f"Error handling Launchpad message: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if Launchpad device is connected."""
        return self._midi.is_connected

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
