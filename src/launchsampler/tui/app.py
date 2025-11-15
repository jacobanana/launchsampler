"""Main unified TUI application with edit and play modes."""

import logging
from functools import wraps
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button, RadioSet
from textual.binding import Binding

from launchsampler.core.player import Player
from launchsampler.models import AppConfig, Launchpad, Set, PlaybackMode, Pad

from launchsampler.protocols import PlaybackEvent

from .services import EditorService
from .widgets import (
    PadGrid,
    PadDetailsPanel,
    StatusBar,
    MoveConfirmationModal,
    ClearConfirmationModal,
    PasteConfirmationModal,
)
from .screens import FileBrowserScreen, DirectoryBrowserScreen, SetFileBrowserScreen, SaveSetBrowserScreen


logger = logging.getLogger(__name__)


def require_mode(*modes):
    """Decorator to restrict action to specific sampler mode(s).

    Args:
        *modes: One or more mode names (e.g., "edit", "play")

    If the app is not in one of the specified modes, the decorated
    method will return immediately without executing.

    Example:
        @require_mode("edit")
        def action_copy_pad(self):
            ...

        @require_mode("edit", "play")
        def action_save(self):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self._sampler_mode not in modes:
                return
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# Convenient mode restriction aliases
edit_only = require_mode("edit")
play_only = require_mode("play")


class LaunchpadSampler(App):
    """
    TUI for Launchpad Sampler.

    This is a THIN UI layer that delegates to:
    - Player: Audio/MIDI/playback logic
    - EditorService: Editing operations

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
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("ctrl+o", "load", "Open Set", show=True),
        Binding("ctrl+l", "open_directory", "Load from Directory", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("b", "browse_sample", "Browse", show=False),
        Binding("c", "clear_pad", "Clear", show=False),
        Binding("ctrl+c", "copy_pad", "Copy", show=True),
        Binding("ctrl+x", "cut_pad", "Cut", show=True),
        Binding("ctrl+v", "paste_pad", "Paste", show=True),
        Binding("space", "toggle_test", "Test/Stop", show=False),
        Binding("1", "set_mode_one_shot", "One-Shot", show=False),
        Binding("2", "set_mode_hold", "Hold", show=False),
        Binding("3", "set_mode_loop", "Loop", show=False),
        Binding("4", "set_mode_loop_toggle", "Loop Toggle", show=False),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("left", "navigate_left", "Left", show=False),
        Binding("right", "navigate_right", "Right", show=False),
        Binding("alt+up", "duplicate_up", "Duplicate Up", show=False),
        Binding("alt+down", "duplicate_down", "Duplicate Down", show=False),
        Binding("alt+left", "duplicate_left", "Duplicate Left", show=False),
        Binding("alt+right", "duplicate_right", "Duplicate Right", show=False),
        Binding("ctrl+up", "move_up", "Move Up", show=False),
        Binding("ctrl+down", "move_down", "Move Down", show=False),
        Binding("ctrl+left", "move_left", "Move Left", show=False),
        Binding("ctrl+right", "move_right", "Move Right", show=False),
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
        self._start_mode = start_mode
        self._sampler_mode = None  # UI mode state (edit/play display)

        # Load or create set
        self.current_set = self._load_initial_set(set_name, samples_dir)

        # Core services (UI-agnostic)
        self.player = Player(config)
        self.editor = EditorService(self.current_set.launchpad, config)

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

        # Load into player if running
        if self.player.is_running:
            self.player.load_set(new_set)

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
        # Start player with initial set
        if not self.player.start(initial_set=self.current_set):
            self.notify("Failed to start player - app may not function correctly", severity="error")

        # Register for playback events
        self.player.set_playback_callback(self._on_playback_event)

        # Set initial mode (UI state only)
        self._set_mode(self._start_mode, notify=False)

        # Select default pad only in edit mode
        if self._start_mode == "edit":
            try:
                self.editor.select_pad(0)
                self._sync_pad_ui(0, select=True)
            except Exception as e:
                logger.error(f"Error selecting default pad: {e}")

        # Start status bar updates
        self.set_interval(0.1, self._update_status_bar)

    def _load_initial_set(self, set_name: Optional[str], samples_dir: Optional[Path]) -> Set:
        """Load initial set configuration."""
        name = set_name or "untitled"

        # Priority 1: Load from samples directory if provided
        if samples_dir:
            try:
                set_obj = Set.from_sample_directory(
                    samples_dir=samples_dir,
                    name=name,
                    auto_configure=True
                )
                logger.info(f"Loaded {len(set_obj.launchpad.assigned_pads)} samples from {samples_dir}")
                return set_obj
            except ValueError as e:
                logger.error(f"Error loading samples: {e}")
                return Set.create_empty(name)

        # Priority 2: Load from saved set file
        if name and name != "untitled":
            set_path = self.config.sets_dir / f"{name}.json"
            if set_path.exists():
                try:
                    set_obj = Set.load_from_file(set_path)
                    logger.info(f"Loaded set: {set_obj.name}")
                    return set_obj
                except Exception as e:
                    logger.error(f"Error loading set: {e}")

        # Fall back to empty set
        logger.info("Created empty set")
        return Set.create_empty(name)

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

        This only affects UI state (what controls are enabled), not hardware.
        MIDI and audio continue running in both modes.

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

        # Update mode
        self._sampler_mode = mode
        self.sub_title = f"{mode.title()}: {self.set_name}"

        # Update UI based on mode
        details = self.query_one(PadDetailsPanel)
        details.set_mode(mode)
        details.display = (mode == "edit")

        # Update grid selection visibility
        grid = self.query_one(PadGrid)
        if mode == "play":
            # Clear selection in play mode
            grid.clear_selection()
        else:
            # Edit mode: ensure a pad is selected
            if self.editor.selected_pad_index is not None:
                # Restore existing selection
                grid.select_pad(self.editor.selected_pad_index)
            else:
                # No pad selected yet, select pad 0 by default
                self.editor.select_pad(0)
                self._sync_pad_ui(0, select=True)

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

    def _on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback events from player.

        Called from audio thread via callback, so use call_from_thread.

        Args:
            event: The playback event that occurred
            pad_index: Index of the pad (0-63)
        """
        # Handle MIDI input events (green border)
        if event == PlaybackEvent.NOTE_ON:
            self.call_from_thread(self._set_pad_midi_on_ui, pad_index, True)
        elif event == PlaybackEvent.NOTE_OFF:
            self.call_from_thread(self._set_pad_midi_on_ui, pad_index, False)
        
        # Handle audio playback events (yellow background)
        elif event == PlaybackEvent.PAD_PLAYING:
            # Pad started playing - show as active
            self.call_from_thread(self._set_pad_playing_ui, pad_index, True)
        elif event in (PlaybackEvent.PAD_STOPPED, PlaybackEvent.PAD_FINISHED):
            # Pad stopped or finished - show as inactive
            self.call_from_thread(self._set_pad_playing_ui, pad_index, False)
        # PAD_TRIGGERED events don't need UI updates (playing will follow immediately)

    def _set_pad_playing_ui(self, pad_index: int, is_playing: bool) -> None:
        """
        Update UI to reflect pad playing state (yellow background).

        Args:
            pad_index: Index of pad (0-63)
            is_playing: Whether pad is playing
        """
        try:
            grid = self.query_one(PadGrid)
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
            grid = self.query_one(PadGrid)
            grid.set_pad_midi_on(pad_index, midi_on)
        except Exception as e:
            logger.debug(f"Error updating pad {pad_index} MIDI state: {e}")

    def _update_status_bar(self) -> None:
        """Update status bar with current state."""
        try:
            status = self.query_one(StatusBar)

            status.update_state(
                mode=self._sampler_mode,
                connected=self.player.is_midi_connected,
                voices=self.player.active_voices,
                audio_device=self.player.audio_device_name,
                midi_device=self.player.midi_device_name
            )
        except Exception:
            # Status bar might not be mounted yet
            pass

    # =================================================================
    # Event Handlers
    # =================================================================

    def on_pad_grid_pad_selected(self, message: PadGrid.PadSelected) -> None:
        """Handle pad selection from grid."""
        if self._sampler_mode == "edit":
            try:
                self.editor.select_pad(message.pad_index)
                self._sync_pad_ui(message.pad_index, select=True)
            except Exception as e:
                logger.error(f"Error selecting pad: {e}")
                self.notify(f"Error selecting pad: {e}", severity="error")

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
            self.action_toggle_test()  # Use same toggle behavior

    @edit_only
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle mode radio button changes."""
        if event.radio_set.id != "mode-radio":
            return

        # Map radio button IDs to playback modes
        mode_map = {
            "mode-oneshot": PlaybackMode.ONE_SHOT,
            "mode-loop": PlaybackMode.LOOP,
            "mode-hold": PlaybackMode.HOLD,
            "mode-looptoggle": PlaybackMode.LOOP_TOGGLE
        }

        pressed_id = event.pressed.id if event.pressed else None
        if pressed_id in mode_map:
            self._set_pad_mode(mode_map[pressed_id])

    @edit_only
    def on_pad_details_panel_volume_changed(self, event: PadDetailsPanel.VolumeChanged) -> None:
        """Handle volume change from details panel."""
        try:
            # Update through editor service
            pad = self.editor.set_pad_volume(event.pad_index, event.volume)

            # Update in audio engine via player
            if self.player._engine:
                self.player._engine.update_pad_volume(event.pad_index, event.volume)

            # Refresh UI
            self._refresh_pad_ui(event.pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating volume: {e}")
            self.notify(f"Error updating volume: {e}", severity="error")

    @edit_only
    def on_pad_details_panel_name_changed(self, event: PadDetailsPanel.NameChanged) -> None:
        """Handle name change from details panel."""
        try:
            # Update through editor service
            pad = self.editor.set_sample_name(event.pad_index, event.name)

            # Refresh UI
            self._refresh_pad_ui(event.pad_index, pad)

        except Exception as e:
            logger.error(f"Error updating name: {e}")
            self.notify(f"Error updating name: {e}", severity="error")

    @edit_only
    def on_pad_details_panel_move_pad_requested(self, event: PadDetailsPanel.MovePadRequested) -> None:
        """Handle move pad request from details panel."""
        try:
            source_index = event.source_index
            target_index = event.target_index
            logger.info(f"Move request received: {source_index} -> {target_index}")

            # Check if target pad has a sample
            target_pad = self.editor.get_pad(target_index)

            if target_pad.is_assigned:
                # Target has a sample - ask user what to do

                logger.info(f"Target pad {target_index} has sample, showing modal")

                # Show modal and handle result via callback
                def handle_move_choice(result: str) -> None:
                    """Handle the user's choice from the modal."""
                    logger.info(f"Modal callback received result: {result}")
                    if result == "cancel":
                        logger.info("User cancelled move")
                        return
                    elif result == "swap":
                        swap = True
                    elif result == "overwrite":
                        swap = False
                    else:
                        logger.warning(f"Unknown result: {result}")
                        return

                    # Perform the move with user's choice
                    logger.info(f"Executing move with swap={swap}")
                    self._execute_pad_move(source_index, target_index, swap)

                self.push_screen(
                    MoveConfirmationModal(
                        source_index=source_index,
                        target_index=target_index,
                        target_sample_name=target_pad.sample.name if target_pad.sample else "Unknown"
                    ),
                    callback=handle_move_choice
                )
                logger.info("Modal pushed, waiting for user input")
            else:
                # Target is empty - just move
                logger.info(f"Target pad {target_index} is empty, moving directly")
                self._execute_pad_move(source_index, target_index, swap=False)

        except Exception as e:
            logger.error(f"Error moving pad: {e}")
            self.notify(f"Error moving pad: {e}", severity="error")

    def _execute_pad_move(self, source_index: int, target_index: int, swap: bool) -> None:
        """
        Execute the actual pad move operation.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            swap: Whether to swap or overwrite
        """
        try:
            logger.info(f"Executing pad move from {source_index} to {target_index} with swap={swap}")
            # Perform the move
            source_pad, target_pad = self.editor.move_pad(source_index, target_index, swap=swap)

            # Reload both pads in audio engine (if running)
            self._reload_pad(source_index)
            self._reload_pad(target_index)

            # Refresh UI for both pads
            self._refresh_pad_ui(source_index, source_pad)
            self._refresh_pad_ui(target_index, target_pad)

            # Update selection based on operation type
            if swap:
                # For swap, keep selection on source pad (both pads still have samples)
                new_selection = source_index
            else:
                # For move/overwrite, follow the sample to target pad
                new_selection = target_index

            # Update editor's selected pad and sync UI
            self.editor.selected_pad_index = new_selection
            self._sync_pad_ui(new_selection, select=True)

            # Show success message
            action = "Swapped" if swap else "Moved"
            self.notify(f"{action} pad {source_index} to {target_index}", severity="information")

        except Exception as e:
            logger.error(f"Error executing pad move: {e}")
            self.notify(f"Error moving pad: {e}", severity="error")

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

    @edit_only
    def action_browse_sample(self) -> None:
        """Open file browser to assign a sample."""
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

    @edit_only
    def action_clear_pad(self) -> None:
        """Clear the selected pad."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        # Check if pad has a sample
        pad = self.editor.get_pad(selected_pad)
        if not pad.is_assigned or not pad.sample:
            self.notify("Pad is already empty", severity="warning")
            return

        # Show confirmation modal
        def handle_confirmation(confirmed: bool) -> None:
            if not confirmed:
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

        self.push_screen(
            ClearConfirmationModal(selected_pad, pad.sample.name),
            handle_confirmation
        )

    @edit_only
    def action_copy_pad(self) -> None:
        """Copy selected pad to clipboard."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        try:
            pad = self.editor.copy_pad(selected_pad)
            self.notify(f"Copied: {pad.sample.name}", severity="information")
        except ValueError as e:
            self.notify(str(e), severity="error")

    @edit_only
    def action_cut_pad(self) -> None:
        """Cut selected pad to clipboard."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        try:
            pad = self.editor.cut_pad(selected_pad)

            # Update audio engine - pad is now empty
            self._reload_pad(selected_pad)

            # Update UI
            self._sync_pad_ui(selected_pad, self.editor.get_pad(selected_pad))

            self.notify(f"Cut: {pad.sample.name}", severity="information")
        except ValueError as e:
            self.notify(str(e), severity="error")

    @edit_only
    def action_paste_pad(self) -> None:
        """Paste clipboard to selected pad."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        if not self.editor.has_clipboard:
            self.notify("Clipboard is empty", severity="warning")
            return

        try:
            # Try paste with overwrite=False first
            pad = self.editor.paste_pad(selected_pad, overwrite=False)

            # Success - update audio and UI
            self._reload_pad(selected_pad)
            self._sync_pad_ui(selected_pad, pad)

            self.notify(f"Pasted: {pad.sample.name}", severity="information")

        except ValueError as e:
            # Check if it's because target is occupied
            if "already has sample" in str(e):
                # Show confirmation modal
                target_pad = self.editor.get_pad(selected_pad)

                def handle_paste_confirm(overwrite: bool) -> None:
                    if overwrite:
                        try:
                            pad = self.editor.paste_pad(selected_pad, overwrite=True)
                            self._reload_pad(selected_pad)
                            self._sync_pad_ui(selected_pad, pad)
                            self.notify(f"Pasted: {pad.sample.name}", severity="information")
                        except Exception as e:
                            logger.error(f"Error pasting: {e}")
                            self.notify(f"Error: {e}", severity="error")

                self.push_screen(
                    PasteConfirmationModal(selected_pad, target_pad.sample.name),
                    handle_paste_confirm
                )
            else:
                # Some other error
                self.notify(str(e), severity="error")

    def _get_directional_target(self, source_index: int, direction: str) -> Optional[int]:
        """Get target pad index from source + direction.

        Args:
            source_index: Current pad index
            direction: One of "up", "down", "left", "right"

        Returns:
            Target pad index, or None if at edge (cannot move in that direction)
        """
        x, y = self.current_set.launchpad.note_to_xy(source_index)

        # Check bounds BEFORE calculating target (like navigation does)
        if direction == "up":
            if y >= 7:  # Already at top
                return None
            y = y + 1
        elif direction == "down":
            if y <= 0:  # Already at bottom
                return None
            y = y - 1
        elif direction == "left":
            if x <= 0:  # Already at left edge
                return None
            x = x - 1
        elif direction == "right":
            if x >= 7:  # Already at right edge
                return None
            x = x + 1
        else:
            return None

        target = self.current_set.launchpad.xy_to_note(x, y)
        return target

    # Duplicate directional operations (Alt+Arrow)

    def action_duplicate_up(self) -> None:
        """Duplicate selected pad upward."""
        self._duplicate_directional("up")

    def action_duplicate_down(self) -> None:
        """Duplicate selected pad downward."""
        self._duplicate_directional("down")

    def action_duplicate_left(self) -> None:
        """Duplicate selected pad to the left."""
        self._duplicate_directional("left")

    def action_duplicate_right(self) -> None:
        """Duplicate selected pad to the right."""
        self._duplicate_directional("right")

    @edit_only
    def _duplicate_directional(self, direction: str) -> None:
        """Duplicate pad in given direction."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        target_index = self._get_directional_target(selected_pad, direction)
        if target_index is None:
            self.notify("Cannot duplicate: At grid edge", severity="warning")
            return

        # Check if source pad has a sample to duplicate
        source_pad = self.editor.get_pad(selected_pad)
        if not source_pad.is_assigned:
            self.notify("No sample to duplicate", severity="warning")
            return

        try:
            # Try duplicate with overwrite=False first
            pad = self.editor.duplicate_pad(selected_pad, target_index, overwrite=False)

            # Success - update audio and UI
            self._reload_pad(target_index)
            self._sync_pad_ui(target_index, pad)

            # Move selection to duplicated pad
            self.editor.select_pad(target_index)
            self._refresh_pad_ui()

            self.notify(f"Duplicated {direction}", severity="information")

        except ValueError as e:
            # Check if it's because target is occupied
            if "already has sample" in str(e):
                # Show confirmation modal
                target_pad = self.editor.get_pad(target_index)

                def handle_duplicate_confirm(overwrite: bool) -> None:
                    if overwrite:
                        try:
                            pad = self.editor.duplicate_pad(selected_pad, target_index, overwrite=True)
                            self._reload_pad(target_index)
                            self._sync_pad_ui(target_index, pad)

                            # Move selection to duplicated pad
                            self.editor.select_pad(target_index)
                            self._refresh_pad_ui()

                            self.notify(f"Duplicated {direction}", severity="information")
                        except Exception as e:
                            logger.error(f"Error duplicating: {e}")
                            self.notify(f"Error: {e}", severity="error")

                from launchsampler.tui.widgets.paste_confirmation_modal import PasteConfirmationModal
                self.push_screen(
                    PasteConfirmationModal(target_index, target_pad.sample.name),
                    handle_duplicate_confirm
                )
            else:
                # Some other error
                self.notify(str(e), severity="error")

    # Move directional operations (Ctrl+Arrow)

    def action_move_up(self) -> None:
        """Move selected pad upward."""
        self._move_directional("up")

    def action_move_down(self) -> None:
        """Move selected pad downward."""
        self._move_directional("down")

    def action_move_left(self) -> None:
        """Move selected pad to the left."""
        self._move_directional("left")

    def action_move_right(self) -> None:
        """Move selected pad to the right."""
        self._move_directional("right")

    @edit_only
    def _move_directional(self, direction: str) -> None:
        """Move pad in given direction."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        target_index = self._get_directional_target(selected_pad, direction)
        if target_index is None:
            self.notify("Cannot move: At grid edge", severity="warning")
            return

        # Check if source pad has a sample to move
        source_pad = self.editor.get_pad(selected_pad)
        if not source_pad.is_assigned:
            self.notify("No sample to move", severity="warning")
            return

        target_pad = self.editor.get_pad(target_index)

        # If target is occupied, show swap confirmation
        if target_pad.is_assigned:
            def handle_move_confirm(swap: bool) -> None:
                if swap:
                    try:
                        source_pad, target_pad = self.editor.move_pad(selected_pad, target_index, swap=True)

                        # Update both pads in audio and UI
                        self._reload_pad(selected_pad)
                        self._reload_pad(target_index)
                        self._sync_pad_ui(selected_pad, source_pad)
                        self._sync_pad_ui(target_index, target_pad)

                        # Move selection to target
                        self.editor.select_pad(target_index)
                        self._refresh_pad_ui()

                        self.notify(f"Swapped {direction}", severity="information")
                    except Exception as e:
                        logger.error(f"Error moving: {e}")
                        self.notify(f"Error: {e}", severity="error")

            from launchsampler.tui.widgets.move_confirmation_modal import MoveConfirmationModal
            self.push_screen(
                MoveConfirmationModal(selected_pad, target_index),
                handle_move_confirm
            )
        else:
            # Move to empty target
            try:
                source_pad, target_pad = self.editor.move_pad(selected_pad, target_index, swap=False)

                # Update both pads in audio and UI
                self._reload_pad(selected_pad)
                self._reload_pad(target_index)
                self._sync_pad_ui(selected_pad, source_pad)
                self._sync_pad_ui(target_index, target_pad)

                # Move selection to target
                self.editor.select_pad(target_index)
                self._refresh_pad_ui()

                self.notify(f"Moved {direction}", severity="information")
            except Exception as e:
                logger.error(f"Error moving: {e}")
                self.notify(f"Error: {e}", severity="error")

    def action_test_pad(self) -> None:
        """Test the selected pad (works in both modes)."""
        if self.editor.selected_pad_index is None:
            return

        pad = self.editor.get_pad(self.editor.selected_pad_index)
        if pad.is_assigned:
            self.player.trigger_pad(self.editor.selected_pad_index)

    def action_toggle_test(self) -> None:
        """Toggle between test and stop for the selected pad."""
        if self.editor.selected_pad_index is None:
            return

        pad = self.editor.get_pad(self.editor.selected_pad_index)
        if not pad.is_assigned:
            return

        # Check if pad is currently playing
        if self.player.is_pad_playing(self.editor.selected_pad_index):
            # Stop the pad - goes through queue and fires proper events
            self.player.stop_pad(self.editor.selected_pad_index)
        else:
            # Start the pad
            self.player.trigger_pad(self.editor.selected_pad_index)

    def action_stop_audio(self) -> None:
        """Stop all audio playback."""
        self.player.stop_all()

        # Also release selected pad if in HOLD mode
        if self.editor.selected_pad_index is not None:
            self.player.release_pad(self.editor.selected_pad_index)

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

    @edit_only
    def _set_pad_mode(self, mode: PlaybackMode) -> None:
        """Set the playback mode for selected pad."""
        selected_pad = self.editor.selected_pad_index
        if selected_pad is None:
            return

        try:
            pad = self.editor.set_pad_mode(selected_pad, mode)

            # Reload in engine
            self._reload_pad(selected_pad)

            # Update UI
            self._sync_pad_ui(selected_pad, pad)

        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_set_mode_one_shot(self) -> None:
        """Set selected pad to one-shot mode."""
        self._set_pad_mode(PlaybackMode.ONE_SHOT)

    def action_set_mode_loop(self) -> None:
        """Set selected pad to loop mode."""
        self._set_pad_mode(PlaybackMode.LOOP)

    def action_set_mode_hold(self) -> None:
        """Set selected pad to hold mode."""
        self._set_pad_mode(PlaybackMode.HOLD)

    def action_set_mode_loop_toggle(self) -> None:
        """Set selected pad to loop toggle mode."""
        self._set_pad_mode(PlaybackMode.LOOP_TOGGLE)

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

    def _reload_pad(self, pad_index: int) -> None:
        """
        Reload a pad in the audio engine after it has been modified.

        This is called after assigning/clearing samples or changing pad modes.

        Args:
            pad_index: Index of pad to reload
        """
        if not self.player._engine:
            return

        pad = self.editor.get_pad(pad_index)

        if pad.is_assigned:
            # Reload the sample into the engine
            self.player._engine.load_sample(pad_index, pad)
        else:
            # Unload the sample from the engine
            self.player._engine.unload_sample(pad_index)

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

            # Get audio data from engine if available
            audio_data = None
            if self.player._engine and pad.is_assigned:
                audio_data = self.player._engine.get_audio_data(pad_index)

            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad, audio_data=audio_data)
        except Exception as e:
            logger.error(f"Error syncing pad UI: {e}")

    # =================================================================
    # Lifecycle
    # =================================================================

    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down application")
        self.player.stop()
