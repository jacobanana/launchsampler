"""Service for managing LED UI synchronization with application state."""

import logging
from typing import TYPE_CHECKING, Optional

from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.devices.launchpad import LaunchpadController
from launchsampler.models import Color
from launchsampler.protocols import (
    AppEvent,
    AppObserver,
    EditEvent,
    EditObserver,
    MidiEvent,
    MidiObserver,
    PlaybackEvent,
    StateObserver,
)
from launchsampler.ui_colors import get_pad_led_color, get_pad_led_palette_index, PANIC_BUTTON_COLOR

if TYPE_CHECKING:
    from launchsampler.models import Pad

logger = logging.getLogger(__name__)


class LEDService(AppObserver, EditObserver, MidiObserver, StateObserver):
    """
    Service for synchronizing the Launchpad LED grid with application state.

    This service observes all system events and updates the Launchpad LEDs
    to mirror the state shown in the TUI. It decouples the application core
    from LED-specific update logic.

    Implements multiple observer protocols:
    - AppObserver: App lifecycle events (SET_MOUNTED, SET_SAVED, etc.)
    - EditObserver: Editing events (PAD_ASSIGNED, PAD_CLEARED, etc.)
    - MidiObserver: MIDI controller events (NOTE_ON, NOTE_OFF, etc.)
    - StateObserver: Playback events (PAD_PLAYING, PAD_STOPPED, etc.)

    LED Color Scheme (synchronized with TUI via ui_colors module):
    - Empty pad: Off (black)
    - Assigned pad: Mode-specific color (red/green/blue/magenta)
    - Playing pad: Pulsing yellow (overrides mode color)
    """

    def __init__(self, controller: Optional[LaunchpadController], orchestrator, state_machine: SamplerStateMachine):
        """
        Initialize the LED service.

        Args:
            controller: The Launchpad controller instance (may be None initially)
            orchestrator: The LaunchpadSamplerApp orchestrator
            state_machine: Shared state machine for querying playback state
        """
        self.controller = controller
        self.orchestrator = orchestrator
        self.state_machine = state_machine
        logger.info("LEDService initialized")

    # =================================================================
    # AppObserver Protocol - App lifecycle events
    # =================================================================

    def on_app_event(self, event: AppEvent, **kwargs) -> None:
        """
        Handle application lifecycle events.

        Args:
            event: The type of application event
            **kwargs: Event-specific data
        """
        try:
            if event == AppEvent.SET_MOUNTED:
                self._handle_set_mounted(**kwargs)
            elif event == AppEvent.SET_SAVED:
                # No LED action needed on save
                pass
            elif event == AppEvent.MODE_CHANGED:
                # No LED action needed on mode change
                pass
            else:
                logger.warning(f"LEDService received unknown app event: {event}")

        except Exception as e:
            logger.error(f"Error handling app event {event}: {e}")

    def _handle_set_mounted(self) -> None:
        """
        Handle SET_MOUNTED event - synchronize LEDs with launchpad state.

        Updates all 64 pad LEDs to reflect the current state.
        """
        try:
            # Update all LEDs
            self._update_all_leds()
            # Light up panic button
            self._set_panic_button_led()
            logger.info("LED grid synchronized with loaded set")

        except Exception as e:
            logger.error(f"Error syncing LEDs with launchpad: {e}")

    # =================================================================
    # EditObserver Protocol - Editing events
    # =================================================================

    def on_edit_event(
        self,
        event: "EditEvent",
        pad_indices: list[int],
        pads: list["Pad"]
    ) -> None:
        """
        Handle editing events and update LEDs.

        This is called when editing operations occur.
        Automatically synchronizes the LEDs with the new pad states.

        Args:
            event: The type of editing event
            pad_indices: List of affected pad indices
            pads: List of affected pad states (post-edit)
        """
        logger.debug(f"LEDService received edit event: {event.value} for pads {pad_indices}")

        try:
            # Update LEDs for edited pads
            for pad_index, pad in zip(pad_indices, pads):
                self._update_pad_led(pad_index, pad)

        except Exception as e:
            logger.error(f"Error handling edit event {event}: {e}")

    # =================================================================
    # MidiObserver Protocol - MIDI controller events
    # =================================================================

    def on_midi_event(self, event: "MidiEvent", pad_index: int, control: int = 0, value: int = 0) -> None:
        """
        Handle MIDI events from controller.

        Called from MIDI thread via LaunchpadController.

        Args:
            event: The MIDI event that occurred
            pad_index: Index of the pad (0-63), or -1 for connection/CC events
            control: MIDI CC control number (for CONTROL_CHANGE events)
            value: MIDI CC value (for CONTROL_CHANGE events)
        """
        logger.debug(f"LEDService received MIDI event: {event}, pad_index: {pad_index}")

        # Handle device connection/disconnection events
        if event == MidiEvent.CONTROLLER_CONNECTED:
            logger.info("Launchpad connected - syncing LED grid")
            # Sync all LEDs when device connects
            self._update_all_leds()
            # Light up panic button
            self._set_panic_button_led()
        elif event == MidiEvent.CONTROLLER_DISCONNECTED:
            logger.info("Launchpad disconnected")
            # Nothing to do - LEDs are already off

        # LED UI doesn't need to react to pad press MIDI events
        # The hardware provides its own tactile feedback when pads are pressed

    # =================================================================
    # StateObserver Protocol - Playback events
    # =================================================================

    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback events from audio engine.

        Called from audio thread via callback.

        Args:
            event: The playback event that occurred
            pad_index: Index of the pad (0-63)
        """
        logger.debug(f"LEDService received playback event: {event}, pad_index: {pad_index}")

        try:
            if event == PlaybackEvent.PAD_PLAYING:
                # Pad started playing - show pulsing yellow
                self._set_pad_playing_led(pad_index, True)

            elif event in (PlaybackEvent.PAD_STOPPED, PlaybackEvent.PAD_FINISHED):
                # Pad stopped or finished - restore normal color
                self._set_pad_playing_led(pad_index, False)

        except Exception as e:
            logger.error(f"Error handling playback event {event}: {e}")

    # =================================================================
    # LED Update Helpers - Private methods to update LEDs
    # =================================================================

    def _update_all_leds(self) -> None:
        """Update all 64 pad LEDs to reflect current state."""
        if not self.controller or not self.controller.is_connected:
            logger.warning("Cannot update LEDs: Controller not available or not connected")
            return

        # Get playing pads from state machine (single source of truth)
        playing_pads = set(self.state_machine.get_playing_pads())

        # Get all pads from orchestrator (single source of truth)
        all_pads = self.orchestrator.launchpad.pads

        # Build bulk update list
        updates = []
        for i in range(64):
            # Check if pad is currently playing
            if i in playing_pads:
                # Playing pads get pulsing yellow (set individually, not in bulk)
                continue  # Skip bulk update, will be set with pulsing after

            pad = all_pads[i]
            if pad.is_assigned:
                # Get color from centralized color scheme
                # This will return mode-specific colors for assigned pads
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

    def _update_pad_led(self, pad_index: int, pad: "Pad") -> None:
        """
        Update LED for a single pad.

        Args:
            pad_index: Index of pad (0-63)
            pad: Pad model
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot update LED: Controller not available or not connected")
            return

        # If pad is playing, don't override the playing animation
        if self.state_machine.is_pad_playing(pad_index):
            return

        # Set color from centralized color scheme
        color = get_pad_led_color(pad, is_playing=False)
        self.controller.set_pad_color(pad_index, color)

    def _set_pad_playing_led(self, pad_index: int, is_playing: bool) -> None:
        """
        Update LED to reflect pad playing state (pulsing yellow).

        Args:
            pad_index: Index of pad (0-63)
            is_playing: Whether pad is playing
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot update LED: Controller not available or not connected")
            return

        if is_playing:
            # Pulse with playing color (centralized from ui_colors)
            pad = self.orchestrator.launchpad.pads[pad_index]
            palette_color = get_pad_led_palette_index(pad, is_playing=True)
            self.controller.set_pad_pulsing(pad_index, palette_color)
        else:
            # Restore normal color
            pad = self.orchestrator.launchpad.pads[pad_index]
            if pad.is_assigned:
                self._update_pad_led(pad_index, pad)
            else:
                self.controller.set_pad_color(pad_index, Color.off())

    def _set_panic_button_led(self) -> None:
        """
        Set the panic button LED to dark red.

        This lights up the control button that triggers the panic function
        (stop all audio) when pressed. The button is identified by the
        configured CC control number.
        """
        if not self.controller or not self.controller.is_connected:
            logger.debug("Cannot set panic button LED: Controller not available or not connected")
            return

        if not self.controller._device:
            logger.debug("Cannot set panic button LED: Device not initialized")
            return

        # Get panic button CC control from config
        cc_control = self.orchestrator.config.panic_button_cc_control

        # Set the LED to dark red using the RGB color
        self.controller._device.output.set_control_led(cc_control, PANIC_BUTTON_COLOR.rgb)
        logger.info(f"Panic button LED set for CC {cc_control}")
