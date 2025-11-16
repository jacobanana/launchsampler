"""Service for managing TUI synchronization with application state."""

import logging
from typing import TYPE_CHECKING

from launchsampler.protocols import AppEvent, AppObserver
from launchsampler.tui.widgets import PadGrid, PadDetailsPanel


if TYPE_CHECKING:
    from launchsampler.tui.app import LaunchpadSampler

logger = logging.getLogger(__name__)


class TUIService(AppObserver):
    """
    Service for synchronizing the Terminal UI with application state.

    This service observes app-level events and updates the TUI components
    (pad grid, details panel) accordingly. It decouples the application core
    from UI-specific update logic.

    Implements AppObserver protocol to receive app lifecycle events.
    """

    def __init__(self, app: "LaunchpadSampler"):
        """
        Initialize the TUI service.

        Args:
            app: The LaunchpadSampler application instance
        """
        self.app = app

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
            if self.app.editor.selected_pad_index is not None:
                self._update_selected_pad_ui(
                    self.app.editor.selected_pad_index,
                    self.app.launchpad.pads[self.app.editor.selected_pad_index]
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
        Handle MODE_CHANGED event.

        Currently a no-op for TUI as mode changes are handled directly
        in app._set_mode(). Included for completeness and future extensions.

        Args:
            **kwargs: Event data (e.g., mode)
        """
        # Mode changes are currently handled directly in app._set_mode()
        # This hook is here for future TUI-specific mode change handling
        pass

    def _update_selected_pad_ui(self, pad_index: int, pad) -> None:
        """
        Update UI for the currently selected pad.

        Helper method to update details panel with pad information.

        Args:
            pad_index: Index of the pad
            pad: Pad model
        """
        try:
            # Fetch audio data if available
            audio_data = None
            if self.app.player._engine and pad.is_assigned:
                audio_data = self.app.player._engine.get_audio_data(pad_index)

            details = self.app.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad, audio_data=audio_data)

        except Exception as e:
            logger.error(f"Error updating selected pad {pad_index} UI: {e}")
