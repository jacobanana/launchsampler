"""Service for managing LED UI synchronization with application state."""

import logging
from typing import TYPE_CHECKING, Optional

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

    LED Color Scheme (mirroring TUI):
    - Empty pad: Off (black)
    - Assigned pad: Pad's configured color (from pad.color)
    - Playing pad: Pulsing yellow
    """

    def __init__(self, controller: Optional[LaunchpadController], orchestrator):
        """
        Initialize the LED service.

        Args:
            controller: The Launchpad controller instance (may be None initially)
            orchestrator: The LaunchpadSamplerApp orchestrator
        """
        self.controller = controller
        self.orchestrator = orchestrator
        self._current_pads: list[Optional["Pad"]] = [None] * 64
        self._playing_pads: set[int] = set()
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
            # Get all pads from orchestrator
            self._current_pads = list(self.orchestrator.launchpad.pads)
            # Update all LEDs
            self._update_all_leds()
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
            # Update internal state and LEDs
            for pad_index, pad in zip(pad_indices, pads):
                self._current_pads[pad_index] = pad
                self._update_pad_led(pad_index, pad)

        except Exception as e:
            logger.error(f"Error handling edit event {event}: {e}")

    # =================================================================
    # MidiObserver Protocol - MIDI controller events
    # =================================================================

    def on_midi_event(self, event: "MidiEvent", pad_index: int) -> None:
        """
        Handle MIDI events from controller.

        Called from MIDI thread via LaunchpadController.

        Args:
            event: The MIDI event that occurred
            pad_index: Index of the pad (0-63), or -1 for connection events
        """
        logger.debug(f"LEDService received MIDI event: {event}, pad_index: {pad_index}")

        # LED UI doesn't need to react to MIDI events (controller already shows feedback)
        # The hardware provides its own tactile feedback when pads are pressed
        pass

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
                self._playing_pads.add(pad_index)
                self._set_pad_playing_led(pad_index, True)

            elif event in (PlaybackEvent.PAD_STOPPED, PlaybackEvent.PAD_FINISHED):
                # Pad stopped or finished - restore normal color
                self._playing_pads.discard(pad_index)
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

        # Build bulk update list
        updates = []
        for i in range(64):
            pad = self._current_pads[i]
            if pad:
                # Use pad's configured color if assigned, otherwise off
                color = pad.color if pad.is_assigned else Color.off()
                updates.append((i, color))
            else:
                # Pad is None, turn off
                updates.append((i, Color.off()))

        # Send bulk update
        self.controller._device.output.set_leds_bulk(updates)
        logger.info(f"Updated all {len(updates)} LEDs")

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
        if pad_index in self._playing_pads:
            return

        # Set color based on pad state
        if pad.is_assigned:
            # Use pad's configured color
            self.controller.set_pad_color(pad_index, pad.color)
        else:
            # Turn off LED for empty pad
            self.controller.set_pad_color(pad_index, Color.off())

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
            # Pulse yellow (palette color 13 is yellow on most Launchpads)
            self.controller.set_pad_pulsing(pad_index, 13)
        else:
            # Restore normal color
            pad = self._current_pads[pad_index]
            if pad:
                self._update_pad_led(pad_index, pad)
            else:
                self.controller.set_pad_color(pad_index, Color.off())
