"""LED rendering logic for Launchpad hardware."""

import logging
from typing import TYPE_CHECKING, Optional

from launchsampler.devices import DeviceController
from launchsampler.models import Color
from launchsampler.ui_shared import get_pad_led_color, get_pad_led_palette_index, PANIC_BUTTON_COLOR

if TYPE_CHECKING:
    from launchsampler.models import Pad

logger = logging.getLogger(__name__)


class LEDRenderer:
    """
    Stateless renderer that translates application state to LED hardware commands.

    This class contains only rendering logic - no event handling or state management.
    It queries state from canonical sources (orchestrator, state_machine) and renders
    the appropriate LED colors.

    Responsibilities:
    - Update individual pad LEDs
    - Update all pad LEDs in bulk
    - Set playing animations (pulsing)
    - Set panic button LED
    """

    def __init__(self, controller: Optional[DeviceController]):
        """
        Initialize the LED renderer.

        Args:
            controller: The device controller instance (may be None initially)
        """
        self.controller = controller
        logger.debug("LEDRenderer initialized")

    def update_all_pads(self, all_pads: list["Pad"], playing_pads: set[int]) -> None:
        """
        Update all 64 pad LEDs to reflect current state.

        Args:
            all_pads: List of all 64 pad states from orchestrator
            playing_pads: Set of pad indices currently playing
        """
        if not self.controller or not self.controller.is_connected:
            logger.warning("Cannot update LEDs: Controller not available or not connected")
            return

        # Build bulk update list for non-playing pads
        updates = []
        for i in range(64):
            # Check if pad is currently playing
            if i in playing_pads:
                # Playing pads get pulsing animation (set individually, not in bulk)
                continue

            pad = all_pads[i]
            if pad.is_assigned:
                # Get color from centralized color scheme
                color = get_pad_led_color(pad, is_playing=False)
                updates.append((i, color))
            else:
                # Pad is empty, turn off
                updates.append((i, Color.off()))

        # Send bulk update for non-playing pads
        if updates:
            self.controller.set_leds_bulk(updates)
            logger.info(f"Updated {len(updates)} non-playing LEDs")

        # Set playing pads with animation
        for pad_index in playing_pads:
            pad = all_pads[pad_index]
            palette_color = get_pad_led_palette_index(pad, is_playing=True)
            self.controller.set_pad_pulsing(pad_index, palette_color)
            logger.debug(f"Set playing animation for pad {pad_index}")

    def update_pad(self, pad_index: int, pad: "Pad", is_playing: bool) -> None:
        """
        Update LED for a single pad.

        Args:
            pad_index: Index of pad (0-63)
            pad: Pad model
            is_playing: Whether this pad is currently playing
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot update LED: Controller not available or not connected")
            return

        # If pad is playing, don't override the playing animation
        if is_playing:
            return

        # Set color from centralized color scheme
        color = get_pad_led_color(pad, is_playing=False)
        self.controller.set_pad_color(pad_index, color)

    def set_playing_animation(self, pad_index: int, pad: "Pad", is_playing: bool) -> None:
        """
        Update LED to reflect pad playing state (pulsing animation).

        Args:
            pad_index: Index of pad (0-63)
            pad: Pad model
            is_playing: Whether pad is playing
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot update LED: Controller not available or not connected")
            return

        if is_playing:
            # Pulse with playing color (centralized from ui_colors)
            palette_color = get_pad_led_palette_index(pad, is_playing=True)
            self.controller.set_pad_pulsing(pad_index, palette_color)
        else:
            # Restore normal color
            if pad.is_assigned:
                self.update_pad(pad_index, pad, is_playing=False)
            else:
                self.controller.set_pad_color(pad_index, Color.off())

    def set_panic_button(self, panic_button_cc: int) -> None:
        """
        Set the panic button LED to dark red.

        Args:
            panic_button_cc: The CC control number for the panic button
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot set panic button LED: Controller not available or not connected")
            return

        if not self.controller._device:
            logger.debug("Cannot set panic button LED: Device not initialized")
            return

        # Set the LED to dark red using the RGB color
        self.controller._device.output.set_control_led(panic_button_cc, PANIC_BUTTON_COLOR.rgb)
        logger.info(f"Panic button LED set for CC {panic_button_cc}")
