"""Main unified TUI application with edit and play modes."""

import logging
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button
from textual.binding import Binding

from launchsampler.audio import AudioDevice
from launchsampler.core.sampler_engine import SamplerEngine
from launchsampler.devices.launchpad import LaunchpadController
from launchsampler.models import AppConfig, Launchpad, Set, PlaybackMode, Pad

from .services import EditorService
from .widgets import PadGrid, PadDetailsPanel, StatusBar
from .screens import FileBrowserScreen, DirectoryBrowserScreen, SetFileBrowserScreen, SaveSetBrowserScreen

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
        Binding("o", "open_directory", "Open Dir", show=True),
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
        samples_dir: Optional[Path] = None,
        start_mode: str = "edit"
    ):
        """
        Initialize the application.

        Args:
            config: Application configuration
            set_name: Name of set to load (None for new set)
            samples_dir: Directory to load samples from (alternative to set_name)
            start_mode: Mode to start in ("edit" or "play")
        """
        super().__init__()
        self.config = config
        self.set_name = set_name or "untitled"
        self.samples_dir = samples_dir
        self._start_mode = start_mode
        self._sampler_mode = None  # Not started yet - will be set in on_mount

        # Track which pads are shown as playing in UI
        self._playing_pads: set[int] = set()

        # Load or create set
        self.current_set = self._load_initial_set()

        # Create editor service
        self.editor = EditorService(self.current_set.launchpad, config)

        # Create audio/MIDI components (direct composition!)
        self._audio_device: Optional[AudioDevice] = None
        self._engine: Optional[SamplerEngine] = None
        self._midi: Optional[LaunchpadController] = None

    @property
    def launchpad(self) -> Launchpad:
        """Get the current launchpad (for backward compatibility)."""
        return self.current_set.launchpad

    def _load_set(self, new_set: Set) -> None:
        """
        Load a new set and update all references.

        This is the single point of truth for loading sets - all load operations
        should go through this method to ensure consistency.

        Args:
            new_set: The Set to load
        """
        # Update current set
        self.current_set = new_set
        self.set_name = new_set.name

        # Update editor reference
        self.editor.launchpad = new_set.launchpad

        # Reload all samples in audio engine if running
        if self._engine:
            self._reload_all_pads()

        # Update grid UI
        grid = self.query_one(PadGrid)
        grid.launchpad = new_set.launchpad
        for i in range(64):
            grid.update_pad(i, new_set.launchpad.pads[i])

        # Update selected pad if one is selected
        if self.editor.selected_pad_index is not None:
            self._sync_pad_ui(self.editor.selected_pad_index, select=True)

        # Update subtitle (only if mode is set)
        if self._sampler_mode:
            self.sub_title = f"{self._sampler_mode.title()}: {self.set_name}"

        logger.info(f"Loaded set: {self.set_name} with {len(new_set.launchpad.assigned_pads)} samples")

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
        # Start in appropriate mode (default to play)
        self._set_mode(self._start_mode, notify=False)

        # Select default pad
        try:
            self.editor.select_pad(0)
            self._sync_pad_ui(0, select=True)
        except Exception as e:
            logger.error(f"Error selecting default pad: {e}")

        # Start status bar updates
        self.set_interval(0.1, self._update_status_bar)

        # Start playback state tracking (check for finished samples)
        self.set_interval(0.05, self._update_playback_states)

    def _load_initial_set(self) -> Set:
        """Load initial set configuration."""
        # Priority 1: Load from samples directory if provided
        if self.samples_dir:
            try:
                set_obj = Set.from_sample_directory(
                    samples_dir=self.samples_dir,
                    name=self.set_name,
                    auto_configure=True
                )
                logger.info(f"Loaded {len(set_obj.launchpad.assigned_pads)} samples from {self.samples_dir}")
                return set_obj
            except ValueError as e:
                logger.error(f"Error loading samples: {e}")
                return Set.create_empty(self.set_name)

        # Priority 2: Load from saved set file
        if self.set_name and self.set_name != "untitled":
            set_path = self.config.sets_dir / f"{self.set_name}.json"
            if set_path.exists():
                try:
                    set_obj = Set.load_from_file(set_path)
                    self.set_name = set_obj.name  # Use name from file
                    logger.info(f"Loaded set: {self.set_name}")
                    return set_obj
                except Exception as e:
                    logger.error(f"Error loading set: {e}")

        # Fall back to empty set
        logger.info("Created empty set")
        return Set.create_empty(self.set_name)

    # =================================================================
    # Mode Switching
    # =================================================================

    def action_switch_mode(self, mode: str) -> None:
        """
        Switch between edit and play modes.

        Args:
            mode: Target mode ("edit" or "play")
        """
        self._set_mode(mode)

    def _set_mode(self, mode: str, notify: bool = True) -> bool:
        """
        Set the mode to edit or play.

        Args:
            mode: Target mode ("edit" or "play")
            notify: Whether to show notification (default: True)

        Returns:
            True if mode was set successfully
        """
        if mode not in ("edit", "play"):
            logger.error(f"Invalid mode: {mode}")
            return False

        # Already in target mode, nothing to do
        if self._sampler_mode == mode:
            return True

        # Start audio if not running
        if not self._engine or not self._engine.is_running:
            if not self._start_audio():
                if notify:
                    self.notify("Failed to start audio", severity="error")
                return False

        # Handle MIDI based on mode
        if mode == "edit":
            # Edit mode: stop MIDI if running
            if self._midi:
                self._stop_midi()
        else:
            # Play mode: start MIDI if not running
            if not self._midi or not self._midi.is_connected:
                if not self._start_midi():
                    if notify:
                        self.notify("Failed to start MIDI controller", severity="error")
                    return False

        # Update mode
        self._sampler_mode = mode
        self.sub_title = f"{mode.title()}: {self.set_name}"

        # Update UI based on mode
        details = self.query_one(PadDetailsPanel)
        details.set_mode(mode)
        details.display = (mode == "edit")

        # Update status bar
        self._update_status_bar()

        # Show notification
        if notify:
            if mode == "edit":
                self.notify("✏ EDIT MODE - Editing enabled", timeout=2)
            else:
                self.notify("▶ PLAY MODE - Editing locked", timeout=2)

        logger.info(f"Switched to {mode} mode")
        return True

    def _update_status_bar(self) -> None:
        """Update status bar with current state."""
        try:
            status = self.query_one(StatusBar)
            status.update_state(
                mode=self._sampler_mode,
                connected=self._midi.is_connected if self._midi else False,
                voices=self._engine.active_voices if self._engine else 0
            )
        except Exception:
            # Status bar might not be mounted yet
            pass

    def _start_audio(self) -> bool:
        """Start audio device and engine."""
        try:
            # Create audio device
            self._audio_device = AudioDevice(
                device=self.config.default_audio_device,
                buffer_size=self.config.default_buffer_size,
                low_latency=True
            )

            # Create engine
            self._engine = SamplerEngine(
                audio_device=self._audio_device,
                num_pads=64
            )

            # Load all assigned pads
            self._reload_all_pads()

            # Start audio
            self._engine.start()
            logger.info("Audio engine started")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio: {e}", exc_info=True)
            self._audio_device = None
            self._engine = None
            return False

    def _stop_audio(self) -> None:
        """Stop audio engine and device."""
        if self._engine:
            self._engine.stop()
            self._engine = None
        self._audio_device = None
        logger.info("Audio engine stopped")

    def _start_midi(self) -> bool:
        """Start MIDI controller."""
        try:
            self._midi = LaunchpadController(
                poll_interval=self.config.midi_poll_interval
            )

            # Wire up event handlers
            self._midi.on_pad_pressed(self._handle_midi_pad_pressed)
            self._midi.on_pad_released(self._handle_midi_pad_released)

            # Start controller
            self._midi.start()
            logger.info("MIDI controller started")
            return True

        except Exception as e:
            logger.error(f"Failed to start MIDI: {e}", exc_info=True)
            self._midi = None
            return False

    def _stop_midi(self) -> None:
        """Stop MIDI controller."""
        if self._midi:
            self._midi.stop()
            self._midi = None
            logger.info("MIDI controller stopped")

    def _reload_all_pads(self) -> None:
        """Reload all pads into audio engine."""
        if not self._engine:
            return

        loaded_count = 0
        for i, pad in enumerate(self.current_set.launchpad.pads):
            if pad.is_assigned:
                if self._engine.load_sample(i, pad):
                    loaded_count += 1

        logger.info(f"Loaded {loaded_count} samples into engine")

    def _reload_pad(self, pad_index: int) -> None:
        """Reload a specific pad into audio engine."""
        if not self._engine:
            return

        pad = self.current_set.launchpad.pads[pad_index]
        if pad.is_assigned:
            self._engine.load_sample(pad_index, pad)
        else:
            self._engine.unload_sample(pad_index)

    def _handle_midi_pad_pressed(self, pad_index: int) -> None:
        """Handle MIDI pad press event."""
        if not self._engine:
            return

        # Trigger audio
        pad = self.current_set.launchpad.pads[pad_index]
        if pad.is_assigned:
            self._engine.trigger_pad(pad_index)

        # Update UI
        self._on_midi_pad_event("pressed", pad_index)

    def _handle_midi_pad_released(self, pad_index: int) -> None:
        """Handle MIDI pad release event."""
        if not self._engine:
            return

        # Release audio (for HOLD/LOOP modes)
        pad = self.current_set.launchpad.pads[pad_index]
        if pad.is_assigned and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
            self._engine.release_pad(pad_index)

        # Update UI
        self._on_midi_pad_event("released", pad_index)

    def _update_playback_states(self) -> None:
        """Check playback states and update UI for finished samples."""
        if not self._playing_pads or not self._engine:
            return

        try:
            grid = self.query_one(PadGrid)

            # Check each pad that's currently marked as playing in UI
            finished_pads = []
            for pad_index in self._playing_pads:
                # Query actual playback state from engine
                playback_info = self._engine.get_playback_info(pad_index)
                if not playback_info or not playback_info.get('is_playing', False):
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
                self._sync_pad_ui(message.pad_index, select=True)
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

    def on_pad_details_panel_volume_changed(self, event: PadDetailsPanel.VolumeChanged) -> None:
        """Handle volume change from details panel."""
        if self._sampler_mode != "edit":
            return

        try:
            # Update through editor service
            pad = self.editor.set_pad_volume(event.pad_index, event.volume)

            # Update in audio engine
            if self._engine:
                self._engine.update_pad_volume(event.pad_index, event.volume)

            # Refresh UI
            self._refresh_pad_ui(event.pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating volume: {e}")
            self.notify(f"Error updating volume: {e}", severity="error")

    def on_pad_details_panel_name_changed(self, event: PadDetailsPanel.NameChanged) -> None:
        """Handle name change from details panel."""
        if self._sampler_mode != "edit":
            return

        try:
            # Update through editor service
            pad = self.editor.set_sample_name(event.pad_index, event.name)

            # Refresh UI
            self._refresh_pad_ui(event.pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating name: {e}")
            self.notify(f"Error updating name: {e}", severity="error")

    def _refresh_pad_ui(self, pad_index: int, pad: Pad) -> None:
        """
        Refresh UI elements for a specific pad.

        Args:
            pad_index: Index of pad to refresh
            pad: Updated pad model
        """
        self._sync_pad_ui(pad_index, pad)

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

        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        # Capture selected pad index (guaranteed not None here)
        selected_pad = self.editor.selected_pad_index

        def handle_file(file_path: Optional[Path]) -> None:
            if file_path:
                try:
                    pad = self.editor.assign_sample(selected_pad, file_path)

                    # Reload in engine
                    self._reload_pad(selected_pad)

                    # Update UI
                    self._sync_pad_ui(selected_pad, pad)

                    # Safe to access sample.name after assign_sample
                    if pad.sample:
                        self.notify(f"Assigned: {pad.sample.name}")
                except Exception as e:
                    logger.error(f"Error assigning sample: {e}")
                    self.notify(f"Error: {e}", severity="error")

        # Start browsing from current samples_root if available, otherwise home
        browse_dir = self.current_set.samples_root if self.current_set.samples_root else Path.home()
        self.push_screen(
            FileBrowserScreen(browse_dir),
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
            self._reload_pad(selected_pad)

            # Update UI
            self._sync_pad_ui(selected_pad, pad)

            self.notify("Pad cleared")
        except Exception as e:
            logger.error(f"Error clearing pad: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_test_pad(self) -> None:
        """Test the selected pad (works in both modes)."""
        if self.editor.selected_pad_index is None:
            return

        pad = self.editor.get_pad(self.editor.selected_pad_index)
        if pad.is_assigned and self._engine:
            self._engine.trigger_pad(self.editor.selected_pad_index)

            # Mark pad as playing in UI
            try:
                grid = self.query_one(PadGrid)
                grid.set_pad_playing(self.editor.selected_pad_index, True)
                self._playing_pads.add(self.editor.selected_pad_index)
            except Exception as e:
                logger.debug(f"Error setting pad playing: {e}")

    def action_stop_audio(self) -> None:
        """Stop all audio playback."""
        if self._engine:
            self._engine.stop_all()

            # Also release selected pad if in HOLD mode
            if self.editor.selected_pad_index is not None:
                self._engine.release_pad(self.editor.selected_pad_index)

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
        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        def handle_save(result: Optional[tuple[Path, str]]) -> None:
            if result:
                directory, filename = result
                try:
                    # Construct full path
                    save_path = directory / f"{filename}.json"
                    
                    # Save set using editor service
                    self.editor.save_set(filename)
                    
                    # Note: The editor service saves to config.sets_dir
                    # If user chose a different directory, we need to also copy/move there
                    if directory != self.config.sets_dir:
                        import shutil
                        src_path = self.config.sets_dir / f"{filename}.json"
                        shutil.copy2(src_path, save_path)
                        self.notify(f"Saved set to: {save_path}")
                    else:
                        self.notify(f"Saved set: {filename}")
                    
                    self.set_name = filename
                    if self._sampler_mode:
                        self.sub_title = f"{self._sampler_mode.title()}: {filename}"
                    
                except Exception as e:
                    logger.error(f"Error saving set: {e}")
                    self.notify(f"Error saving: {e}", severity="error")

        # Start in the sets directory
        self.push_screen(
            SaveSetBrowserScreen(self.config.sets_dir, self.set_name),
            handle_save
        )

    def action_load(self) -> None:
        """Load a saved set."""
        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        def handle_load(set_path: Optional[Path]) -> None:
            if set_path:
                try:
                    # Load set from file
                    set_obj = Set.load_from_file(set_path)

                    # Use single load method
                    self._load_set(set_obj)

                    self.notify(f"Loaded set: {set_obj.name}")

                except Exception as e:
                    logger.error(f"Error loading set: {e}")
                    self.notify(f"Error loading: {e}", severity="error")

        # Start in the sets directory
        self.push_screen(SetFileBrowserScreen(self.config.sets_dir), handle_load)

    def action_open_directory(self) -> None:
        """Open a directory to load samples from."""
        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        def handle_directory_selected(dir_path: Optional[Path]) -> None:
            if dir_path:
                try:
                    # Create a new Set from the directory
                    new_set = Set.from_sample_directory(
                        samples_dir=dir_path,
                        name="untitled",
                        auto_configure=True
                    )

                    # Use single load method
                    self._load_set(new_set)

                    # Switch to edit mode after loading directory
                    self._set_mode("edit")

                    self.notify(f"Loaded {len(new_set.launchpad.assigned_pads)} samples from {dir_path.name}")

                except Exception as e:
                    logger.error(f"Error loading directory: {e}")
                    self.notify(f"Error loading directory: {e}", severity="error")

        # Start browsing from current samples_root if available, otherwise home
        start_dir = self.current_set.samples_root if self.current_set.samples_root else Path.home()
        self.push_screen(DirectoryBrowserScreen(start_dir), handle_directory_selected)

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
            self._reload_pad(selected_pad)

            # Update UI
            self._sync_pad_ui(selected_pad, pad)

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
                self._sync_pad_ui(new_index, select=True)
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
                self._sync_pad_ui(new_index, select=True)
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
                self._sync_pad_ui(new_index, select=True)
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
                self._sync_pad_ui(new_index, select=True)
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    # =================================================================
    # UI Updates
    # =================================================================

    def _sync_pad_ui(self, pad_index: int, pad: Optional[Pad] = None, *, select: bool = False) -> None:
        """
        Synchronize UI widgets with pad state.

        Args:
            pad_index: Index of pad to sync
            pad: Pad model (fetched if None)
            select: If True, update grid selection; if False, update grid content
        """
        try:
            if pad is None:
                pad = self.editor.get_pad(pad_index)

            grid = self.query_one(PadGrid)
            if select:
                grid.select_pad(pad_index)
            else:
                grid.update_pad(pad_index, pad)

            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad)
        except Exception as e:
            logger.error(f"Error syncing pad UI: {e}")

    # =================================================================
    # Lifecycle
    # =================================================================

    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down application")
        self._stop_midi()
        self._stop_audio()
