"""Event handler for LED UI synchronization with application state."""

import logging
from typing import TYPE_CHECKING

from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.led_ui.services.led_renderer import LEDRenderer
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


class LEDEventHandler(AppObserver, EditObserver, MidiObserver, StateObserver):
    """
    Event handler for synchronizing the Launchpad LED grid with application state.

    This service observes all system events and delegates LED rendering to LEDRenderer.
    It decouples the application core from LED-specific update logic.

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

    def __init__(self, renderer: LEDRenderer, orchestrator, state_machine: SamplerStateMachine):
        """
        Initialize the LED event handler.

        Args:
            renderer: The LED renderer for hardware updates
            orchestrator: The LaunchpadSamplerApp orchestrator
            state_machine: Shared state machine for querying playback state
        """
        self.renderer = renderer
        self.orchestrator = orchestrator
        self.state_machine = state_machine
        logger.info("LEDEventHandler initialized")

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
                logger.warning(f"LEDEventHandler received unknown app event: {event}")

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
        logger.debug(f"LEDEventHandler received edit event: {event.value} for pads {pad_indices}")

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
        logger.debug(f"LEDEventHandler received MIDI event: {event}, pad_index: {pad_index}")

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
        logger.debug(f"LEDEventHandler received playback event: {event}, pad_index: {pad_index}")

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
    # LED Update Helpers - Delegate to renderer
    # =================================================================

    def _update_all_leds(self) -> None:
        """Update all 64 pad LEDs to reflect current state."""
        # Get playing pads from state machine (single source of truth)
        playing_pads = set(self.state_machine.get_playing_pads())

        # Get all pads from orchestrator (single source of truth)
        all_pads = self.orchestrator.launchpad.pads

        # Delegate to renderer
        self.renderer.update_all_pads(all_pads, playing_pads)

    def _update_pad_led(self, pad_index: int, pad: "Pad") -> None:
        """
        Update LED for a single pad.

        Args:
            pad_index: Index of pad (0-63)
            pad: Pad model
        """
        # Check if pad is currently playing
        is_playing = self.state_machine.is_pad_playing(pad_index)

        # Delegate to renderer
        self.renderer.update_pad(pad_index, pad, is_playing)

    def _set_pad_playing_led(self, pad_index: int, is_playing: bool) -> None:
        """
        Update LED to reflect pad playing state (pulsing animation).

        Args:
            pad_index: Index of pad (0-63)
            is_playing: Whether pad is playing
        """
        # Get pad from orchestrator (single source of truth)
        pad = self.orchestrator.launchpad.pads[pad_index]

        # Delegate to renderer
        self.renderer.set_playing_animation(pad_index, pad, is_playing)

    def _set_panic_button_led(self) -> None:
        """
        Set the panic button LED to dark red.

        This lights up the control button that triggers the panic function
        (stop all audio) when pressed.
        """
        # Get panic button CC control from config
        cc_control = self.orchestrator.config.panic_button_cc_control

        # Delegate to renderer
        self.renderer.set_panic_button(cc_control)
