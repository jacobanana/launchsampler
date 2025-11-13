"""Main unified TUI application with edit and play modes."""

import logging
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button
from textual.binding import Binding

from launchsampler.models import AppConfig, Launchpad, Set, PlaybackMode

from .services import EditorService, SamplerService
from .widgets import PadGrid, PadDetailsPanel, StatusBar
from .screens import FileBrowserScreen, SaveSetScreen, LoadSetScreen

logger = logging.getLogger(__name__)


class LaunchpadSampler(App):
    """
    Unified TUI application for editing and playing Launchpad sets.

    Provides two modes:
    - Edit Mode: Build sets, assign samples, test with preview audio
    - Play Mode: Full MIDI integration for live performance

    Switch modes anytime with E (edit) or P (play) keys.
    """

    TITLE = "Launchpad Sampler"
    CSS_PATH = None  # Using widget DEFAULT_CSS

    BINDINGS = [
        Binding("e", "switch_mode('edit')", "Edit Mode", show=True),
        Binding("p", "switch_mode('play')", "Play Mode", show=True),
        Binding("s", "save", "Save", show=True),
        Binding("l", "load", "Load", show=True),
        Binding("b", "browse_sample", "Browse", show=False),
        Binding("c", "clear_pad", "Clear", show=False),
        Binding("t", "test_pad", "Test", show=False),
        Binding("escape", "stop_audio", "Stop", show=False),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("left", "navigate_left", "Left", show=False),
        Binding("right", "navigate_right", "Right", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        config: AppConfig,
        set_name: Optional[str] = None,
        start_mode: str = "edit"
    ):
        """
        Initialize the application.

        Args:
            config: Application configuration
            set_name: Name of set to load (None for new set)
            start_mode: Mode to start in ("edit" or "play")
        """
        super().__init__()
        self.config = config
        self.set_name = set_name or "untitled"
        self._start_mode = start_mode
        self._sampler_mode = "play"  # Don't use _current_mode (conflicts with Textual)

        # Track which pads are shown as playing in UI
        self._playing_pads: set[int] = set()

        # Load or create launchpad
        self.launchpad = self._load_initial_launchpad()

        # Create services (composition!)
        self.editor = EditorService(self.launchpad, config)
        self.sampler = SamplerService(
            self.launchpad,
            config,
            on_pad_event=self._on_midi_pad_event
        )

    def compose(self) -> ComposeResult:
        """Create the main layout."""
        yield Header(show_clock=True)

        with Horizontal():
            yield PadGrid(self.launchpad)
            yield PadDetailsPanel()

        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Set initial subtitle (must be done after mount)
        self.sub_title = f"Play: {self.set_name}"

        # Start in appropriate mode (default to play)
        if self._start_mode == "edit":
            self._enter_edit_mode()
        else:
            self._enter_play_mode()

        # Select default pad
        try:
            self.editor.select_pad(0)
            self._update_ui_for_selection(0)
        except Exception as e:
            logger.error(f"Error selecting default pad: {e}")

        # Start status bar updates
        self.set_interval(0.1, self._update_status_bar)

        # Start playback state tracking (check for finished samples)
        self.set_interval(0.05, self._update_playback_states)

    def _load_initial_launchpad(self) -> Launchpad:
        """Load initial launchpad configuration."""
        if self.set_name and self.set_name != "untitled":
            set_path = self.config.sets_dir / f"{self.set_name}.json"
            if set_path.exists():
                try:
                    set_obj = Set.load_from_file(set_path)
                    logger.info(f"Loaded set: {self.set_name}")
                    return set_obj.launchpad
                except Exception as e:
                    logger.error(f"Error loading set: {e}")

        # Try loading from samples directory
        if self.config.samples_dir.exists():
            try:
                launchpad = Launchpad.from_sample_directory(
                    samples_dir=self.config.samples_dir,
                    auto_configure=True
                )
                logger.info("Loaded samples from directory")
                return launchpad
            except ValueError as e:
                logger.warning(f"Error loading samples: {e}")

        # Fall back to empty launchpad
        logger.info("Created empty launchpad")
        return Launchpad.create_empty()

    # =================================================================
    # Mode Switching
    # =================================================================

    def action_switch_mode(self, mode: str) -> None:
        """
        Switch between edit and play modes.

        Args:
            mode: Target mode ("edit" or "play")
        """
        if mode == "play" and self._sampler_mode == "edit":
            self._enter_play_mode()
        elif mode == "edit" and self._sampler_mode == "play":
            self._exit_play_mode()

    def _enter_edit_mode(self) -> None:
        """Enter edit mode (audio + MIDI with editing enabled)."""
        # Start with full audio + MIDI (same as play mode)
        if self.sampler.start_play_mode():
            self._sampler_mode = "edit"
            self.sub_title = f"Edit: {self.set_name}"
            self.notify("✏ EDIT MODE - Editing enabled", timeout=2)

            # Enable edit controls
            details = self.query_one(PadDetailsPanel)
            details.set_mode("edit")

            # Update status bar
            self._update_status_bar()

            logger.info("Entered edit mode")
        else:
            self.notify("Failed to start edit mode", severity="error")

    def _enter_play_mode(self) -> None:
        """Enter play mode (audio + MIDI with editing disabled)."""
        # Already running from edit mode, just change UI state
        if self._sampler_mode == "edit":
            # Already have audio + MIDI, just update UI
            self._sampler_mode = "play"
            self.sub_title = f"Play: {self.set_name}"
            self.notify("▶ PLAY MODE - Editing locked", timeout=2)

            # Disable edit controls
            details = self.query_one(PadDetailsPanel)
            details.set_mode("play")

            # Update status bar
            self._update_status_bar()

            logger.info("Entered play mode")
        else:
            # Cold start in play mode
            if self.sampler.start_play_mode():
                self._sampler_mode = "play"
                self.sub_title = f"Play: {self.set_name}"
                self.notify("▶ PLAY MODE - Editing locked", timeout=2)

                # Disable edit controls
                details = self.query_one(PadDetailsPanel)
                details.set_mode("play")

                # Update status bar
                self._update_status_bar()

                logger.info("Entered play mode")
            else:
                self.notify(
                    "Failed to start play mode - check MIDI connection",
                    severity="error"
                )

    def _exit_play_mode(self) -> None:
        """Exit play mode (back to edit mode)."""
        # Keep audio + MIDI running, just change UI state
        self._sampler_mode = "edit"
        self.sub_title = f"Edit: {self.set_name}"
        self.notify("✏ EDIT MODE - Editing enabled", timeout=2)

        # Enable edit controls
        details = self.query_one(PadDetailsPanel)
        details.set_mode("edit")

        # Update status bar
        self._update_status_bar()

        logger.info("Exited play mode")

    def _update_status_bar(self) -> None:
        """Update status bar with current state."""
        try:
            status = self.query_one(StatusBar)
            status.update_state(
                mode=self._sampler_mode,
                connected=self.sampler.is_connected,
                voices=self.sampler.active_voices
            )
        except Exception:
            # Status bar might not be mounted yet
            pass

    def _update_playback_states(self) -> None:
        """Check playback states and update UI for finished samples."""
        if not self._playing_pads:
            return

        try:
            grid = self.query_one(PadGrid)

            # Check each pad that's currently marked as playing in UI
            finished_pads = []
            for pad_index in self._playing_pads:
                # Query actual playback state from engine
                if not self.sampler.is_pad_playing(pad_index):
                    # Pad has finished playing
                    grid.set_pad_playing(pad_index, False)
                    finished_pads.append(pad_index)

            # Remove finished pads from tracking set
            for pad_index in finished_pads:
                self._playing_pads.discard(pad_index)

        except Exception as e:
            logger.debug(f"Error updating playback states: {e}")

    # =================================================================
    # Event Handlers
    # =================================================================

    def _on_midi_pad_event(self, event_type: str, pad_index: int) -> None:
        """
        Handle pad events from MIDI (for visual feedback).

        Args:
            event_type: "pressed" or "released"
            pad_index: Index of pad (0-63)
        """
        if event_type == "pressed":
            # Mark pad as playing in UI for visual feedback
            try:
                grid = self.query_one(PadGrid)
                grid.set_pad_playing(pad_index, True)
                self._playing_pads.add(pad_index)
            except Exception as e:
                logger.debug(f"Error setting pad playing: {e}")

    def on_pad_grid_pad_selected(self, message: PadGrid.PadSelected) -> None:
        """Handle pad selection from grid."""
        if self._sampler_mode == "edit":
            try:
                self.editor.select_pad(message.pad_index)
                self._update_ui_for_selection(message.pad_index)
            except Exception as e:
                logger.error(f"Error selecting pad: {e}")
                self.notify(f"Error selecting pad: {e}", severity="error")
        else:
            self.notify("Switch to edit mode to select pads", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses from details panel."""
        button_id = event.button.id

        if not button_id:
            return

        if button_id == "browse-btn":
            self.action_browse_sample()
        elif button_id == "clear-btn":
            self.action_clear_pad()
        elif button_id == "test-btn":
            self.action_test_pad()
        elif button_id == "stop-btn":
            self.action_stop_audio()
        elif button_id.startswith("mode-"):
            # Mode button pressed
            mode_name = button_id.replace("mode-", "").upper()
            if mode_name == "ONESHOT":
                mode_name = "ONE_SHOT"
            try:
                mode = PlaybackMode(mode_name.lower())
                self._set_pad_mode(mode)
            except ValueError:
                logger.error(f"Invalid mode: {mode_name}")

    # =================================================================
    # Actions
    # =================================================================

    def action_browse_sample(self) -> None:
        """Open file browser to assign a sample."""
        if self._sampler_mode != "edit":
            self.notify("Switch to edit mode first", severity="warning")
            return

        if self.editor.selected_pad_index is None:
            self.notify("Select a pad first", severity="warning")
            return

        # Capture selected pad index (guaranteed not None here)
        selected_pad = self.editor.selected_pad_index

        def handle_file(file_path: Optional[Path]) -> None:
            if file_path:
                try:
                    pad = self.editor.assign_sample(selected_pad, file_path)

                    # Reload in engine
                    self.sampler.reload_pad(selected_pad)

                    # Update UI
                    self._update_ui_for_pad(selected_pad, pad)

                    # Safe to access sample.name after assign_sample
                    if pad.sample:
                        self.notify(f"Assigned: {pad.sample.name}")
                except Exception as e:
                    logger.error(f"Error assigning sample: {e}")
                    self.notify(f"Error: {e}", severity="error")

        self.push_screen(
            FileBrowserScreen(self.config.samples_dir),
            handle_file
        )

    def action_clear_pad(self) -> None:
        """Clear the selected pad."""
        if self._sampler_mode != "edit":
            self.notify("Switch to edit mode first", severity="warning")
            return

        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        try:
            pad = self.editor.clear_pad(selected_pad)

            # Unload from engine
            self.sampler.reload_pad(selected_pad)

            # Update UI
            self._update_ui_for_pad(selected_pad, pad)

            self.notify("Pad cleared")
        except Exception as e:
            logger.error(f"Error clearing pad: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_test_pad(self) -> None:
        """Test the selected pad (works in both modes)."""
        if self.editor.selected_pad_index is None:
            return

        pad = self.launchpad.pads[self.editor.selected_pad_index]
        if pad.is_assigned:
            self.sampler.trigger_pad(self.editor.selected_pad_index)

            # Mark pad as playing in UI
            try:
                grid = self.query_one(PadGrid)
                grid.set_pad_playing(self.editor.selected_pad_index, True)
                self._playing_pads.add(self.editor.selected_pad_index)
            except Exception as e:
                logger.debug(f"Error setting pad playing: {e}")

    def action_stop_audio(self) -> None:
        """Stop all audio playback."""
        self.sampler.stop_all()

        # Also release selected pad if in HOLD mode
        if self.editor.selected_pad_index is not None:
            self.sampler.release_pad(self.editor.selected_pad_index)

        # Clear all playing pad indicators in UI
        try:
            grid = self.query_one(PadGrid)
            for pad_index in list(self._playing_pads):
                grid.set_pad_playing(pad_index, False)
            self._playing_pads.clear()
        except Exception as e:
            logger.debug(f"Error clearing pad indicators: {e}")

    def action_save(self) -> None:
        """Save the current set."""
        def handle_save(name: Optional[str]) -> None:
            if name:
                try:
                    self.editor.save_set(name)
                    self.set_name = name
                    self.sub_title = f"{self._sampler_mode.title()}: {name}"
                    self.notify(f"Saved set: {name}")
                except Exception as e:
                    logger.error(f"Error saving set: {e}")
                    self.notify(f"Error saving: {e}", severity="error")

        self.push_screen(SaveSetScreen(self.set_name), handle_save)

    def action_load(self) -> None:
        """Load a saved set."""
        def handle_load(set_path: Optional[Path]) -> None:
            if set_path:
                try:
                    set_obj = self.editor.load_set(set_path)

                    # Update launchpad reference
                    self.launchpad = set_obj.launchpad
                    self.sampler.launchpad = self.launchpad

                    # Reload all samples in engine
                    self.sampler.reload_all()

                    # Update grid
                    grid = self.query_one(PadGrid)
                    grid.launchpad = self.launchpad
                    for i in range(64):
                        grid.update_pad(i, self.launchpad.pads[i])

                    # Update selected pad if one is selected
                    if self.editor.selected_pad_index is not None:
                        self._update_ui_for_selection(self.editor.selected_pad_index)

                    self.set_name = set_obj.name
                    self.sub_title = f"{self._sampler_mode.title()}: {self.set_name}"
                    self.notify(f"Loaded set: {set_obj.name}")

                except Exception as e:
                    logger.error(f"Error loading set: {e}")
                    self.notify(f"Error loading: {e}", severity="error")

        self.push_screen(LoadSetScreen(self.config.sets_dir), handle_load)

    def _set_pad_mode(self, mode: PlaybackMode) -> None:
        """Set the playback mode for selected pad."""
        if self._sampler_mode != "edit":
            self.notify("Switch to edit mode first", severity="warning")
            return

        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            return

        try:
            pad = self.editor.set_pad_mode(selected_pad, mode)

            # Reload in engine
            self.sampler.reload_pad(selected_pad)

            # Update UI
            self._update_ui_for_pad(selected_pad, pad)

            self.notify(f"Mode: {mode.value}")
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            self.notify(f"Error: {e}", severity="error")

    # =================================================================
    # Navigation
    # =================================================================

    def action_navigate_up(self) -> None:
        """Navigate to pad above current selection."""
        if self._sampler_mode != "edit" or self.editor.selected_pad_index is None:
            return

        x = self.editor.selected_pad_index % 8
        y = self.editor.selected_pad_index // 8

        if y < 7:
            new_index = (y + 1) * 8 + x
            try:
                self.editor.select_pad(new_index)
                self._update_ui_for_selection(new_index)
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_down(self) -> None:
        """Navigate to pad below current selection."""
        if self._sampler_mode != "edit" or self.editor.selected_pad_index is None:
            return

        x = self.editor.selected_pad_index % 8
        y = self.editor.selected_pad_index // 8

        if y > 0:
            new_index = (y - 1) * 8 + x
            try:
                self.editor.select_pad(new_index)
                self._update_ui_for_selection(new_index)
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_left(self) -> None:
        """Navigate to pad left of current selection."""
        if self._sampler_mode != "edit" or self.editor.selected_pad_index is None:
            return

        x = self.editor.selected_pad_index % 8
        y = self.editor.selected_pad_index // 8

        if x > 0:
            new_index = y * 8 + (x - 1)
            try:
                self.editor.select_pad(new_index)
                self._update_ui_for_selection(new_index)
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_right(self) -> None:
        """Navigate to pad right of current selection."""
        if self._sampler_mode != "edit" or self.editor.selected_pad_index is None:
            return

        x = self.editor.selected_pad_index % 8
        y = self.editor.selected_pad_index // 8

        if x < 7:
            new_index = y * 8 + (x + 1)
            try:
                self.editor.select_pad(new_index)
                self._update_ui_for_selection(new_index)
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    # =================================================================
    # UI Updates
    # =================================================================

    def _update_ui_for_selection(self, pad_index: int) -> None:
        """Update UI after pad selection."""
        try:
            pad = self.launchpad.pads[pad_index]

            grid = self.query_one(PadGrid)
            grid.select_pad(pad_index)

            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad)
        except Exception as e:
            logger.error(f"Error updating UI for selection: {e}")

    def _update_ui_for_pad(self, pad_index: int, pad) -> None:
        """Update UI after pad modification."""
        try:
            grid = self.query_one(PadGrid)
            grid.update_pad(pad_index, pad)

            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad)
        except Exception as e:
            logger.error(f"Error updating UI for pad: {e}")

    # =================================================================
    # Lifecycle
    # =================================================================

    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down application")
        self.sampler.stop()
