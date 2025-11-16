"""Service for managing TUI synchronization with application state."""

import logging
from typing import TYPE_CHECKING, Optional

from launchsampler.protocols import (
    AppEvent,
    AppObserver,
    EditEvent,
    EditObserver,
    MidiEvent,
    MidiObserver,
    PlaybackEvent,
    SelectionEvent,
    SelectionObserver,
    StateObserver,
)
from launchsampler.tui.widgets import PadGrid, PadDetailsPanel, StatusBar

if TYPE_CHECKING:
    from launchsampler.models import Pad
    from launchsampler.tui.app import LaunchpadSampler

logger = logging.getLogger(__name__)


class TUIService(AppObserver, EditObserver, SelectionObserver, MidiObserver, StateObserver):
    """
    Service for synchronizing the Terminal UI with application state.

    This service observes all system events and updates the TUI components
    (pad grid, details panel, status bar) accordingly. It decouples the
    application core from UI-specific update logic.

    Implements multiple observer protocols:
    - AppObserver: App lifecycle events (SET_LOADED, SET_SAVED, etc.)
    - EditObserver: Editing events (PAD_ASSIGNED, PAD_CLEARED, etc.)
    - SelectionObserver: Selection events (CHANGED, CLEARED) - UI state only
    - MidiObserver: MIDI controller events (NOTE_ON, NOTE_OFF, etc.)
    - StateObserver: Playback events (PAD_PLAYING, PAD_STOPPED, etc.)
    """

    def __init__(self, app: "LaunchpadSampler"):
        """
        Initialize the TUI service.

        Args:
            app: The LaunchpadSampler application instance
        """
        self.app = app

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
            if event == AppEvent.SET_LOADED:
                self._handle_set_loaded()
            elif event == AppEvent.SET_SAVED:
                self._handle_set_saved(**kwargs)
            elif event == AppEvent.MODE_CHANGED:
                self._handle_mode_changed(**kwargs)
            else:
                logger.warning(f"TUIService received unknown app event: {event}")

        except Exception as e:
            logger.error(f"Error handling app event {event}: {e}")

    def _handle_set_loaded(self) -> None:
        """
        Handle SET_LOADED event - synchronize UI with launchpad state.

        Updates all 64 pads and the details panel if a pad is selected.
        """
        try:
            grid = self.app.query_one(PadGrid)

            # Update all pads in the grid
            for i, pad in enumerate(self.app.launchpad.pads):
                grid.update_pad(i, pad)

            # Update details panel if a pad is currently selected
            if self.app.selected_pad_index is not None:
                self._update_selected_pad_ui(
                    self.app.selected_pad_index,
                    self.app.launchpad.pads[self.app.selected_pad_index]
                )

            logger.debug("TUI synchronized with loaded set")

        except Exception as e:
            logger.error(f"Error syncing UI with launchpad: {e}")

    def _handle_set_saved(self, **kwargs) -> None:
        """
        Handle SET_SAVED event.

        Currently a no-op for TUI, but included for completeness.
        Future: Could update status bar or show save confirmation.

        Args:
            **kwargs: Event data (e.g., path, set_name)
        """
        # TUI doesn't need to do anything special when a set is saved
        # Status notifications are handled elsewhere
        pass

    def _handle_mode_changed(self, **kwargs) -> None:
        """
        Handle MODE_CHANGED event - update status bar.

        Updates the status bar to reflect the new mode.

        Args:
            **kwargs: Event data (e.g., mode)
        """
        # Update status bar when mode changes
        self._update_status_bar()

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
        Handle editing events and update UI.

        This is called from the UI thread when editing operations occur.
        Automatically synchronizes the UI with the new pad states.

        Args:
            event: The type of editing event
            pad_indices: List of affected pad indices
            pads: List of affected pad states (post-edit)
        """
        logger.debug(f"TUIService received edit event: {event.value} for pads {pad_indices}")

        try:
            # Update content - refresh grid and details if currently selected
            for pad_index, pad in zip(pad_indices, pads):
                self._update_pad_ui(pad_index, pad)

        except Exception as e:
            logger.error(f"Error handling edit event {event}: {e}")

    # =================================================================
    # SelectionObserver Protocol - Selection events
    # =================================================================

    def on_selection_event(
        self,
        event: "SelectionEvent",
        pad_index: Optional[int]
    ) -> None:
        """
        Handle selection change events.

        This is the NEW way to handle selection (replaces EditEvent.PAD_SELECTED).
        Selection is UI state that doesn't affect persistence or audio.

        Args:
            event: The type of selection event
            pad_index: Index of selected pad (0-63), or None if cleared
        """
        logger.debug(f"TUIService received selection event: {event.value}, pad: {pad_index}")

        try:
            if event == SelectionEvent.CHANGED and pad_index is not None:
                # Pad selected - update UI
                pad = self.app.editor.get_pad(pad_index)
                self._update_selected_pad_ui(pad_index, pad)
            elif event == SelectionEvent.CLEARED:
                # Selection cleared - update UI
                grid = self.app.query_one(PadGrid)
                grid.clear_selection()

        except Exception as e:
            logger.error(f"Error handling selection event {event}: {e}")

    # =================================================================
    # MidiObserver Protocol - MIDI controller events
    # =================================================================

    def on_midi_event(self, event: "MidiEvent", pad_index: int) -> None:
        """
        Handle MIDI events from controller.

        Called from MIDI thread via LaunchpadController, so use call_from_thread.

        Args:
            event: The MIDI event that occurred
            pad_index: Index of the pad (0-63), or -1 for connection events
        """
        if event == MidiEvent.NOTE_ON:
            # MIDI note on - show green border
            self.app.call_from_thread(self._set_pad_midi_on_ui, pad_index, True)

        elif event == MidiEvent.NOTE_OFF:
            # MIDI note off - remove green border
            self.app.call_from_thread(self._set_pad_midi_on_ui, pad_index, False)

        elif event in (MidiEvent.CONTROLLER_CONNECTED, MidiEvent.CONTROLLER_DISCONNECTED):
            # MIDI controller connection changed - update status bar
            self.app.call_from_thread(self._update_status_bar)

    # =================================================================
    # StateObserver Protocol - Playback events
    # =================================================================

    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback events from audio engine.

        Called from audio thread via callback, so use call_from_thread.

        Args:
            event: The playback event that occurred
            pad_index: Index of the pad (0-63)
        """
        # Handle audio playback events (yellow background)
        if event == PlaybackEvent.PAD_PLAYING:
            # Pad started playing - show as active
            self.app.call_from_thread(self._set_pad_playing_ui, pad_index, True)
            # Update status bar for voice count
            self.app.call_from_thread(self._update_status_bar)

        elif event in (PlaybackEvent.PAD_STOPPED, PlaybackEvent.PAD_FINISHED):
            # Pad stopped or finished - show as inactive
            self.app.call_from_thread(self._set_pad_playing_ui, pad_index, False)
            # Update status bar for voice count
            self.app.call_from_thread(self._update_status_bar)

        # PAD_TRIGGERED events don't need UI updates (playing will follow immediately)

    # =================================================================
    # UI Update Helpers - Private methods to update widgets
    # =================================================================

    def _update_status_bar(self) -> None:
        """Update status bar with current state."""
        try:
            status = self.app.query_one(StatusBar)

            status.update_state(
                mode=self.app._sampler_mode,
                connected=self.app.player.is_midi_connected,
                voices=self.app.player.active_voices,
                audio_device=self.app.player.audio_device_name,
                midi_device=self.app.player.midi_device_name
            )
        except Exception:
            # Status bar might not be mounted yet
            pass

    def _update_details_panel(self, pad_index: int, pad: "Pad") -> None:
        """
        Update the details panel for a pad.

        Fetches audio data from the engine if available and updates the panel.

        Args:
            pad_index: Index of pad
            pad: Pad model
        """
        audio_data = None
        if self.app.player._engine and pad.is_assigned:
            audio_data = self.app.player._engine.get_audio_data(pad_index)

        details = self.app.query_one(PadDetailsPanel)
        details.update_for_pad(pad_index, pad, audio_data=audio_data)

    def _update_selected_pad_ui(self, pad_index: int, pad: Optional["Pad"] = None) -> None:
        """
        Update UI for pad selection.

        Updates both grid selection and details panel.

        Args:
            pad_index: Index of pad to select
            pad: Pad model (fetched if None)
        """
        try:
            if pad is None:
                pad = self.app.editor.get_pad(pad_index)

            # Update grid selection
            grid = self.app.query_one(PadGrid)
            grid.select_pad(pad_index)

            # Update details panel
            self._update_details_panel(pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating selected pad {pad_index} UI: {e}")

    def _update_pad_ui(self, pad_index: int, pad: Optional["Pad"] = None) -> None:
        """
        Update UI for pad content changes.

        Updates grid and details panel if pad is currently selected.

        Args:
            pad_index: Index of pad to update
            pad: Pad model (fetched if None)
        """
        try:
            if pad is None:
                pad = self.app.editor.get_pad(pad_index)

            # Update grid
            grid = self.app.query_one(PadGrid)
            grid.update_pad(pad_index, pad)

            # Update details panel if this pad is currently selected
            if pad_index == self.app.selected_pad_index:
                self._update_details_panel(pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating pad {pad_index} UI: {e}")

    def _set_pad_playing_ui(self, pad_index: int, is_playing: bool) -> None:
        """
        Update UI to reflect pad playing state (yellow background).

        Args:
            pad_index: Index of pad (0-63)
            is_playing: Whether pad is playing
        """
        try:
            grid = self.app.query_one(PadGrid)
            grid.set_pad_playing(pad_index, is_playing)
        except Exception as e:
            logger.debug(f"Error updating pad {pad_index} playing state: {e}")

    def _set_pad_midi_on_ui(self, pad_index: int, midi_on: bool) -> None:
        """
        Update UI to reflect MIDI note on/off state (green border).

        Args:
            pad_index: Index of pad (0-63)
            midi_on: Whether MIDI note is held
        """
        try:
            grid = self.app.query_one(PadGrid)
            grid.set_pad_midi_on(pad_index, midi_on)
        except Exception as e:
            logger.debug(f"Error updating pad {pad_index} MIDI state: {e}")
