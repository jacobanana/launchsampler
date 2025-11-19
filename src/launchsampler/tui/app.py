"""Main unified TUI application with edit and play modes."""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button, RadioSet
from textual.binding import Binding

from launchsampler.core.player import Player
from launchsampler.models import Launchpad, Set, PlaybackMode
from launchsampler.services import EditorService, SetManagerService
from launchsampler.protocols import AppEvent, SelectionEvent, UIAdapter

from .decorators import edit_only, handle_action_errors
from .services import TUIService, NavigationService
from .widgets import (
    PadGrid,
    PadDetailsPanel,
    StatusBar,
    MoveConfirmationModal,
    ClearConfirmationModal,
    PasteConfirmationModal,
)
from .screens import FileBrowserScreen, DirectoryBrowserScreen, SetFileBrowserScreen, SaveSetBrowserScreen

if TYPE_CHECKING:
    from launchsampler.app import LaunchpadSamplerApp

logger = logging.getLogger(__name__)


class LaunchpadSampler(App):
    """
    Textual TUI for Launchpad Sampler.

    This is a PURE UI layer that delegates all business logic to the orchestrator.
    The orchestrator (LaunchpadSamplerApp) owns all state and services.

    Implements UIAdapter protocol via structural subtyping (no explicit inheritance
    to avoid metaclass conflicts between App and Protocol).

    Responsibilities:
    - Textual framework integration (widgets, layouts, bindings)
    - UI event handling (keyboard, mouse)
    - Visual presentation and updates via TUIService

    The orchestrator provides:
    - Core state (launchpad, current_set, mode)
    - Services (Player, EditorService, SetManagerService)
    - Observer pattern for UI synchronization

    Modes:
    - Edit Mode: Build sets, assign samples, configure pads
    - Play Mode: Full MIDI integration for live performance

    Switch modes anytime with E (edit) or P (play) keys.
    """

    TITLE = "Launchpad Sampler"

    BINDINGS = [
        Binding("e", "switch_mode('edit')", "Edit Mode", show=True),
        Binding("p", "switch_mode('play')", "Play Mode", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("ctrl+o", "load", "Open Set", show=True),
        Binding("ctrl+l", "open_directory", "Load from Directory", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("escape", "stop_audio", "Panic (Stop All)", show=True),
        Binding("b", "browse_sample", "Browse", show=False),
        Binding("c", "copy_pad", "Copy", show=True),
        Binding("x", "cut_pad", "Cut", show=True),
        Binding("v", "paste_pad", "Paste", show=True),
        Binding("d", "delete_pad", "Delete", show=True),
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

    # =================================================================
    # Initialization & Lifecycle - App setup, Textual lifecycle hooks
    # =================================================================

    def __init__(
        self,
        orchestrator: "LaunchpadSamplerApp",
        start_mode: str = "play"
    ):
        """
        Initialize the Textual UI application.

        This is a thin UI layer that delegates all business logic to the orchestrator.
        The orchestrator should NOT be initialized yet - call orchestrator.initialize()
        after registering this UI to ensure event synchronization.

        Args:
            orchestrator: The LaunchpadSamplerApp orchestrator instance (not yet initialized)
            start_mode: Mode to start in ("edit" or "play")
        """
        super().__init__()

        # Orchestrator owns all business logic and state
        self.orchestrator = orchestrator
        self.config = orchestrator.config
        self._start_mode = start_mode

        # UI-specific ephemeral state (not persisted)
        self._selected_pad_index: Optional[int] = None

        # Services
        self.tui_service: Optional[TUIService] = None  # Initialized in initialize()
        self.navigation: NavigationService = NavigationService(orchestrator.launchpad)

        self._selection_observers: list = []  # For SelectionObserver pattern
        self._initialized = False  # Track initialization state
        self._startup_error: Optional[Exception] = None  # Store startup errors to display after exit
        logger.info("LaunchpadSampler TUI created")

    # =================================================================
    # UIAdapter Protocol Implementation
    # =================================================================

    def initialize(self) -> None:
        """
        Initialize the TUI and register observers.

        This is called by orchestrator.run() to set up the TUI service
        and register app-level observers.
        """
        if self._initialized:
            logger.warning("TUI already initialized")
            return

        logger.info("Initializing TUI service and registering observers")

        # Create TUI service - handles ALL UI updates via observer pattern
        self.tui_service = TUIService(self)

        # Register TUI service for app-level events (SET_MOUNTED, MODE_CHANGED)
        self.orchestrator.register_observer(self.tui_service)

        # Register for selection events (UI-specific state)
        self.register_selection_observer(self.tui_service)

        self._initialized = True
        logger.info("TUI initialization complete - ready to receive events")

    def register_with_services(self, orchestrator: "LaunchpadSamplerApp") -> None:
        """
        Register TUI service with orchestrator services.

        Called by orchestrator.initialize() after services are created
        but BEFORE events are fired. This ensures we receive all edit events.

        Args:
            orchestrator: The orchestrator with initialized services
        """
        if not self.tui_service:
            raise RuntimeError("TUI service not initialized - call initialize() first")

        logger.info("Registering TUI service with orchestrator services")

        # Register for edit events
        orchestrator.editor.register_observer(self.tui_service)

        # Register for MIDI events (for visual feedback - green borders)
        if orchestrator.midi_controller:
            orchestrator.midi_controller.register_observer(self.tui_service)
            logger.info("TUI service registered as MIDI observer")

        # Register for playback events
        orchestrator.player.set_playback_callback(self.tui_service.on_playback_event)

        logger.info("TUI service registered with all orchestrator services")

    def run(self) -> None:
        """
        Run the Textual TUI (blocks until app exits).

        This is called by the orchestrator after initialization completes.
        The orchestrator has already fired startup events which the TUI received.

        Raises:
            RuntimeError: If a startup error occurred (e.g., audio device in use)
        """
        if not self._initialized:
            raise RuntimeError("TUI must be initialized before running")

        logger.info("Starting Textual TUI")
        # Call Textual's run method (blocks until app exits)
        super().run()

        # After Textual exits, check if there was a startup error
        # Re-raise the original exception to preserve type and attributes
        if self._startup_error:
            raise self._startup_error

    def shutdown(self) -> None:
        """
        Shutdown the TUI and clean up resources.

        Called by the orchestrator during application exit.
        """
        logger.info("Shutting down TUI")
        # Unregister observers
        if self.tui_service:
            self.orchestrator.unregister_observer(self.tui_service)
            if self.orchestrator.editor:
                self.orchestrator.editor.unregister_observer(self.tui_service)

    # =================================================================
    # Read-Only State Access - Delegated to orchestrator
    #
    # ARCHITECTURAL RULE: These properties provide READ-ONLY access.
    #
    # ❌ NEVER do this:
    #    self.launchpad.pads[i] = new_pad  # Direct mutation!
    #
    # ✅ ALWAYS do this:
    #    self.editor.assign_sample(i, sample)  # Service method fires events
    #
    # Why? Because services fire events that keep all observers in sync.
    # Direct mutations break the observer pattern and cause UI desync.
    # =================================================================

    @property
    def launchpad(self) -> Launchpad:
        """
        READ-ONLY access to launchpad state.

        Do NOT mutate this directly. Use EditorService methods to make
        changes (they fire events for observer synchronization).
        """
        return self.orchestrator.launchpad

    @property
    def current_set(self) -> Set:
        """
        READ-ONLY access to current set.

        To change sets, use orchestrator.mount_set() which fires
        AppEvent.SET_MOUNTED for observers.
        """
        return self.orchestrator.current_set

    @property
    def set_manager(self) -> SetManagerService:
        """Get the set manager service from orchestrator."""
        return self.orchestrator.set_manager

    @property
    def player(self) -> Player:
        """Get the player service from orchestrator."""
        return self.orchestrator.player

    @property
    def editor(self) -> EditorService:
        """Get the editor service from orchestrator."""
        return self.orchestrator.editor

    @property
    def _sampler_mode(self) -> Optional[str]:
        """
        READ-ONLY access to current mode.

        To change mode, use orchestrator.set_mode() or _set_mode()
        which fires AppEvent.MODE_CHANGED.
        """
        return self.orchestrator.mode

    # =================================================================
    # Selection Management (UI-Specific Ephemeral State)
    #
    # Selection is UI state that doesn't persist to disk.
    # Each UI can have its own independent selection.
    # =================================================================

    @property
    def selected_pad_index(self) -> Optional[int]:
        """Get the currently selected pad index (UI state)."""
        return self._selected_pad_index

    def select_pad(self, pad_index: int) -> None:
        """
        Select a pad (UI operation).

        This updates UI-specific selection state and notifies selection observers.
        This does NOT modify persistent data or fire EditEvent.

        Args:
            pad_index: Index of pad to select (0-63)
        """
        if not 0 <= pad_index < 64:
            logger.error(f"Pad index {pad_index} out of range")
            return

        self._selected_pad_index = pad_index

        # Notify selection observers (TUIService will update UI)
        self._notify_selection_observers(SelectionEvent.CHANGED, pad_index)

    def clear_pad_selection(self) -> None:
        """Clear pad selection (UI operation - renamed to avoid Textual API conflict)."""
        self._notify_selection_observers(SelectionEvent.CLEARED, None)

    def register_selection_observer(self, observer) -> None:
        """Register an observer for selection events."""
        if observer not in self._selection_observers:
            self._selection_observers.append(observer)

    def _notify_selection_observers(self, event, pad_index: Optional[int]) -> None:
        """Notify all selection observers."""
        for observer in self._selection_observers:
            try:
                observer.on_selection_event(event, pad_index)
            except Exception as e:
                logger.error(f"Error notifying selection observer: {e}")

    # =================================================================
    # Textual Lifecycle
    # =================================================================

    def compose(self) -> ComposeResult:
        """Create the main layout."""
        yield Header(show_clock=True)

        with Horizontal():
            yield PadGrid()  # No launchpad parameter - data-driven
            yield PadDetailsPanel()

        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        """
        Initialize the app after Textual mounting.

        At this point, Textual is running with its event loop active,
        so we can safely process events and update widgets.

        Flow:
        1. UIAdapter.initialize() has created TUI service and registered app observers
        2. Now Textual is running (we're in on_mount)
        3. Initialize the grid widgets
        4. Initialize the orchestrator (fires SET_MOUNTED, MODE_CHANGED)
        5. TUI service receives events and updates widgets (now they exist!)
        """
        if not self._initialized or not self.tui_service:
            raise RuntimeError("TUI must be initialized via UIAdapter.initialize() before mounting")

        logger.info("TUI mounting - Textual is now running")

        # Initialize grid with launchpad (creates button widgets)
        grid = self.query_one(PadGrid)
        grid.initialize_pads(self.launchpad)

        # NOW initialize the orchestrator (Textual is running, widgets exist)
        # orchestrator.initialize() will:
        # 1. Create services (SetManager, Player, Editor)
        # 2. Call ui.register_with_services() to register observers
        # 3. Fire SET_MOUNTED and MODE_CHANGED events (TUI service receives and processes them)
        logger.info("Initializing orchestrator from TUI on_mount")
        try:
            self.orchestrator.initialize()
        except Exception as e:
            # Handle initialization errors (e.g., audio device in use)
            # Store the full exception object (not just string) to preserve
            # custom exception attributes like recovery hints
            logger.error(f"Failed to initialize orchestrator: {e}")

            # Store exception to display after Textual exits
            self._startup_error = e

            # Exit the app with error code
            self.exit(1)
            return

        # Update subtitle (events have already synced the widgets)
        if self.orchestrator.mode:
            self.sub_title = f"{self.orchestrator.mode.title()}: {self.current_set.name}"

        logger.info("TUI mount complete - orchestrator initialized, UI synchronized")

    def on_unmount(self) -> None:
        """
        Cleanup when Textual app unmounts.

        Note: Orchestrator shutdown is handled by orchestrator.shutdown(),
        which calls our UIAdapter.shutdown() method. We don't call it here
        to avoid double-shutdown.
        """
        logger.info("TUI unmounted")

    def _notify_app_observers(self, event: AppEvent, **kwargs) -> None:
        """
        Notify all registered app observers of an event.

        Delegates to orchestrator's notification system.

        Args:
            event: The app event that occurred
            **kwargs: Event-specific data
        """
        self.orchestrator._notify_observers(event, **kwargs)

    # =================================================================
    # Set Management - Loading and managing sample sets
    # =================================================================

    def _load_set(self, loaded_set: Set) -> None:
        """
        Mount a set into the app.

        Delegates to orchestrator's mount_set method which activates the Set
        in the running application (updates state, syncs player, fires events).

        Args:
            loaded_set: The Set to mount (already loaded from disk/directory)
        """
        # Delegate to orchestrator
        self.orchestrator.mount_set(loaded_set)

        # Update subtitle
        if self._sampler_mode:
            self.sub_title = f"{self._sampler_mode.title()}: {self.current_set.name}"

    # =================================================================
    # Mode Management - Edit/Play mode switching
    # =================================================================

    def action_switch_mode(self, mode: str) -> None:
        """
        Switch between edit and play modes.
        
        Entry point for keybindings (E/P keys). Delegates to _set_mode.

        Args:
            mode: Target mode ("edit" or "play")
        """
        self._set_mode(mode)

    def _set_mode_ui(self, mode: str) -> None:
        """
        Update UI to reflect the current mode.

        This is called by the TUI service when MODE_CHANGED event is received.
        It only updates UI state (selection, details panel visibility).
        Does NOT call orchestrator - that would create a feedback loop!

        Args:
            mode: Current mode ("edit" or "play")
        """
        if mode not in ("edit", "play"):
            logger.error(f"Invalid mode: {mode}")
            return

        # Update subtitle
        self.sub_title = f"{mode.title()}: {self.current_set.name}"

        details = self.query_one(PadDetailsPanel)
        if mode == "play":
            # Clear pad selection in play mode
            self.clear_pad_selection()
            # Hide details panel in play mode
            details.display = False
        else:
            # Edit mode: show details panel and restore/set selection
            # Setting display=True makes the panel queryable for the SelectionEvent handler
            details.display = True

            # Ensure a pad is selected - SelectionEvent will update the details panel
            if self.selected_pad_index is not None:
                # Restore existing selection - SelectionEvent will update UI
                self.select_pad(self.selected_pad_index)
            else:
                # No pad selected yet, select pad 0 by default
                self.select_pad(0)

        logger.info(f"UI updated for {mode} mode")

    def _set_mode(self, mode: str) -> bool:
        """
        Change the application mode (edit or play).

        This delegates to the orchestrator, which will fire MODE_CHANGED event,
        which will trigger _set_mode_ui() to update the UI.

        This only affects UI state (what controls are enabled), not hardware.
        MIDI and audio continue running in both modes.

        Args:
            mode: Target mode ("edit" or "play")

        Returns:
            True if mode was set successfully
        """
        if mode not in ("edit", "play"):
            logger.error(f"Invalid mode: {mode}")
            return False

        # Delegate to orchestrator to update mode
        # Orchestrator will fire MODE_CHANGED event
        # TUI service will receive event and call _set_mode_ui()
        success = self.orchestrator.set_mode(mode)

        logger.info(f"Mode change requested: {mode}, success: {success}")
        return success

    # =================================================================
    # Widget Message Handlers - Handle messages from Textual widgets
    # =================================================================

    def on_pad_grid_pad_selected(self, message: PadGrid.PadSelected) -> None:
        """Handle pad selection from grid."""
        if self._sampler_mode == "edit":
            try:
                self.select_pad(message.pad_index)  # Fires SelectionEvent
            except Exception as e:
                logger.error(f"Error selecting pad: {e}")
                self.notify(f"Error selecting pad: {e}", severity="error")
        elif self._sampler_mode == "play":
            # In play mode, clicking a pad triggers it (same as spacebar)
            pad = self.editor.get_pad(message.pad_index)
            if not pad.is_assigned:
                return

            # Toggle playback: stop if playing, start if not
            if self.player.is_pad_playing(message.pad_index):
                self.player.stop_pad(message.pad_index)
            else:
                self.player.trigger_pad(message.pad_index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses from details panel."""
        button_id = event.button.id

        if not button_id:
            return

        if button_id == "browse-btn":
            self.action_browse_sample()
        elif button_id == "clear-btn":
            self.action_delete_pad()
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
            # Update through editor service (events handle audio/UI sync automatically)
            _ = self.editor.set_pad_volume(event.pad_index, event.volume)

        except Exception as e:
            logger.error(f"Error updating volume: {e}")
            self.notify(f"Error updating volume: {e}", severity="error")

    @edit_only
    def on_pad_details_panel_name_changed(self, event: PadDetailsPanel.NameChanged) -> None:
        """Handle name change from details panel."""
        try:
            # Update through editor service (events handle UI sync automatically)
            _ = self.editor.set_sample_name(event.pad_index, event.name)

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
                    self._perform_pad_move(source_index, target_index, swap)

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
                self._perform_pad_move(source_index, target_index, swap=False)

        except Exception as e:
            logger.error(f"Error moving pad: {e}")
            self.notify(f"Error moving pad: {e}", severity="error")

    # =================================================================
    # User Actions - File Operations - Load/save sets and browse samples
    # =================================================================

    @edit_only
    def action_browse_sample(self) -> None:
        """Open file browser to assign a sample."""
        if self.selected_pad_index is None:
            self.notify("Select a pad first", severity="warning")
            return

        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        # Capture selected pad index (guaranteed not None here)
        selected_pad = self.selected_pad_index

        def handle_file(file_path: Optional[Path]) -> None:
            if file_path:
                try:
                    # Assign sample (events handle audio/UI sync automatically)
                    pad = self.editor.assign_sample(selected_pad, file_path)

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

                    # Save set using orchestrator (handles name changes internally)
                    self.orchestrator.save_set(save_path, name=filename)

                    self.notify(f"Saved set to: {save_path}")

                    # Update subtitle
                    if self._sampler_mode:
                        self.sub_title = f"{self._sampler_mode.title()}: {filename}"

                except Exception as e:
                    logger.error(f"Error saving set: {e}", exc_info=True)
                    self.notify(f"Error saving: {e}", severity="error")

        # Start in the sets directory
        self.push_screen(
            SaveSetBrowserScreen(self.config.sets_dir, self.current_set.name),
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
                    # Load set using SetManagerService
                    loaded_set = self.set_manager.open_set(set_path)

                    # Use single load method
                    self._load_set(loaded_set)

                    self.notify(f"Loaded set: {loaded_set.name}")

                except Exception as e:
                    logger.error(f"Error loading set: {e}")
                    self.notify("Error loading set file", severity="error")

        # Start in the sets directory
        self.push_screen(SetFileBrowserScreen(self.set_manager, self.config.sets_dir), handle_load)

    def action_open_directory(self) -> None:
        """Open a directory to load samples from."""
        # Don't open modal if one is already open
        if len(self.screen_stack) > 1:
            return

        def handle_directory_selected(dir_path: Optional[Path]) -> None:
            if dir_path:
                try:
                    # Load samples using SetManagerService
                    loaded_set = self.set_manager.create_from_directory(dir_path, dir_path.name)

                    # Use single load method
                    self._load_set(loaded_set)

                    # Switch to edit mode after loading directory
                    self._set_mode("edit")

                    self.notify(f"Loaded {len(self.launchpad.assigned_pads)} samples from {dir_path.name}")

                except Exception as e:
                    logger.error(f"Error loading directory: {e}")
                    self.notify(f"Error loading directory: {e}", severity="error")

        # Start browsing from current samples_root if available, otherwise home
        start_dir = self.current_set.samples_root if self.current_set.samples_root else Path.home()
        self.push_screen(DirectoryBrowserScreen(start_dir), handle_directory_selected)

    # =================================================================
    # User Actions - Pad Editing - Copy, cut, paste, delete operations
    # =================================================================

    @edit_only
    def action_copy_pad(self) -> None:
        """Copy selected pad to clipboard."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        try:
            pad = self.editor.copy_pad(selected_pad)
            self.notify(f"Copied: {pad.sample.name}", severity="information")
        except ValueError as e:
            self.notify(str(e), severity="error")

    @edit_only
    @handle_action_errors("cut pad")
    def action_cut_pad(self) -> None:
        """Cut selected pad to clipboard."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        # Stop playback if pad is playing (PAD_STOPPED event will update UI)
        if self.player.is_pad_playing(selected_pad):
            self.player.stop_pad(selected_pad)

        # Cut pad (events handle audio/UI sync automatically)
        pad = self.editor.cut_pad(selected_pad)

        self.notify(f"Cut: {pad.sample.name}", severity="information")

    @edit_only
    def action_paste_pad(self) -> None:
        """Paste clipboard to selected pad."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        if not self.editor.has_clipboard:
            self.notify("Clipboard is empty", severity="warning")
            return

        try:
            # Try paste with overwrite=False first (events handle audio/UI sync automatically)
            pad = self.editor.paste_pad(selected_pad, overwrite=False)

            self.notify(f"Pasted: {pad.sample.name}", severity="information")

        except ValueError as e:
            # Check if it's because target is occupied
            if "already has sample" in str(e):
                # Show confirmation modal
                target_pad = self.editor.get_pad(selected_pad)

                def handle_paste_confirm(overwrite: bool) -> None:
                    if overwrite:
                        try:
                            # Paste (events handle audio/UI sync automatically)
                            pad = self.editor.paste_pad(selected_pad, overwrite=True)
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

    @edit_only
    def action_delete_pad(self) -> None:
        """Delete the selected pad."""
        selected_pad = self.selected_pad_index
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
                # Clear pad (events handle audio/UI sync automatically)
                _ = self.editor.clear_pad(selected_pad)

                self.notify("Pad deleted")
            except Exception as e:
                logger.error(f"Error deleting pad: {e}")
                self.notify(f"Error: {e}", severity="error")

        self.push_screen(
            ClearConfirmationModal(selected_pad, pad.sample.name),
            handle_confirmation
        )

    # =================================================================
    # User Actions - Pad Operations - Navigate, duplicate, move pads
    # =================================================================

    def action_navigate_up(self) -> None:
        """Navigate to pad above current selection."""
        if self._sampler_mode != "edit" or self.selected_pad_index is None:
            return

        new_index = self.navigation.get_neighbor(self.selected_pad_index, "up")
        if new_index is not None:
            try:
                self.select_pad(new_index)  # Event system handles UI sync
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_down(self) -> None:
        """Navigate to pad below current selection."""
        if self._sampler_mode != "edit" or self.selected_pad_index is None:
            return

        new_index = self.navigation.get_neighbor(self.selected_pad_index, "down")
        if new_index is not None:
            try:
                self.select_pad(new_index)  # Event system handles UI sync
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_left(self) -> None:
        """Navigate to pad left of current selection."""
        if self._sampler_mode != "edit" or self.selected_pad_index is None:
            return

        new_index = self.navigation.get_neighbor(self.selected_pad_index, "left")
        if new_index is not None:
            try:
                self.select_pad(new_index)  # Event system handles UI sync
            except Exception as e:
                logger.error(f"Error navigating: {e}")

    def action_navigate_right(self) -> None:
        """Navigate to pad right of current selection."""
        if self._sampler_mode != "edit" or self.selected_pad_index is None:
            return

        new_index = self.navigation.get_neighbor(self.selected_pad_index, "right")
        if new_index is not None:
            try:
                self.select_pad(new_index)  # Event system handles UI sync
            except Exception as e:
                logger.error(f"Error navigating: {e}")

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

    # =================================================================
    # User Actions - Playback - Test pads and control playback modes
    # =================================================================

    def action_test_pad(self) -> None:
        """Test the selected pad (works in both modes)."""
        if self.selected_pad_index is None:
            return

        pad = self.editor.get_pad(self.selected_pad_index)
        if pad.is_assigned:
            self.player.trigger_pad(self.selected_pad_index)

    def action_toggle_test(self) -> None:
        """Toggle between test and stop for the selected pad."""
        if self.selected_pad_index is None:
            return

        pad = self.editor.get_pad(self.selected_pad_index)
        if not pad.is_assigned:
            return

        # Check if pad is currently playing
        if self.player.is_pad_playing(self.selected_pad_index):
            # Stop the pad - goes through queue and fires proper events
            self.player.stop_pad(self.selected_pad_index)
        else:
            # Start the pad
            self.player.trigger_pad(self.selected_pad_index)

    def action_stop_audio(self) -> None:
        """Stop all audio playback."""
        self.player.stop_all()

        # Also release selected pad if in HOLD mode
        if self.selected_pad_index is not None:
            self.player.release_pad(self.selected_pad_index)

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
    # Operation Helpers - Internal helpers for pad operations
    # =================================================================

    @edit_only
    def _duplicate_directional(self, direction: str) -> None:
        """Duplicate pad in given direction."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        target_index = self.navigation.get_neighbor(selected_pad, direction)  # type: ignore
        if target_index is None:
            self.notify("Cannot duplicate: At grid edge", severity="warning")
            return

        # Check if source pad has a sample to duplicate
        source_pad = self.editor.get_pad(selected_pad)
        if not source_pad.is_assigned:
            self.notify("No sample to duplicate", severity="warning")
            return

        try:
            # Try duplicate with overwrite=False first (events handle audio/UI sync automatically)
            pad = self.editor.duplicate_pad(selected_pad, target_index, overwrite=False)

            # Move selection to duplicated pad
            self.select_pad(target_index)
            # Selection event will sync UI automatically

        except ValueError as e:
            # Check if it's because target is occupied
            if "already has sample" in str(e):
                # Show confirmation modal
                target_pad = self.editor.get_pad(target_index)

                def handle_duplicate_confirm(overwrite: bool) -> None:
                    if overwrite:
                        try:
                            # Duplicate (events handle audio/UI sync automatically)
                            pad = self.editor.duplicate_pad(selected_pad, target_index, overwrite=True)

                            # Move selection to duplicated pad
                            self.select_pad(target_index)  # Event system handles UI sync

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

    @edit_only
    def _move_directional(self, direction: str) -> None:
        """Move pad in given direction."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            self.notify("Select a pad first", severity="warning")
            return

        target_index = self.navigation.get_neighbor(selected_pad, direction)  # type: ignore
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
            def handle_move_confirm(action: str) -> None:
                if action == "cancel":
                    return
                
                swap = (action == "swap")
                
                # Stop playback if pads are playing
                source_was_playing = self.player.is_pad_playing(selected_pad)
                target_was_playing = self.player.is_pad_playing(target_index)

                if source_was_playing:
                    self.player.stop_pad(selected_pad)
                if target_was_playing:
                    self.player.stop_pad(target_index)

                # Perform the move operation
                self._perform_pad_move(selected_pad, target_index, swap)

                # Note: UI will update automatically via PAD_STOPPED events

            self.push_screen(
                MoveConfirmationModal(selected_pad, target_index, target_pad.sample.name),
                handle_move_confirm
            )
        else:
            # Move to empty target
            # Stop playback if source pad is playing
            was_playing = self.player.is_pad_playing(selected_pad)
            if was_playing:
                self.player.stop_pad(selected_pad)

            # Perform the move operation
            self._perform_pad_move(selected_pad, target_index, swap=False)

            # Note: UI will update automatically via PAD_STOPPED event

    def _perform_pad_move(self, source_index: int, target_index: int, swap: bool) -> None:
        """
        Perform pad move operation after confirmation.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            swap: Whether to swap or overwrite
        """
        try:
            logger.info(f"Executing pad move from {source_index} to {target_index} with swap={swap}")
            # Perform the move (events handle audio/UI sync automatically)
            source_pad, target_pad = self.editor.move_pad(source_index, target_index, swap=swap)

            # Update selection based on operation type
            if swap:
                # For swap, keep selection on source pad (both pads still have samples)
                new_selection = source_index
            else:
                # For move/overwrite, follow the sample to target pad
                new_selection = target_index

            # Update editor's selected pad (event system handles UI sync)
            self.select_pad(new_selection)

        except Exception as e:
            logger.error(f"Error executing pad move: {e}")
            self.notify(f"Error moving pad: {e}", severity="error")

    @edit_only
    def _set_pad_mode(self, mode: PlaybackMode) -> None:
        """Set the playback mode for selected pad."""
        selected_pad = self.selected_pad_index
        if selected_pad is None:
            return

        try:
            # Check if mode is actually changing to avoid unnecessary reloads
            current_pad = self.editor.get_pad(selected_pad)
            if current_pad.mode == mode:
                # Mode hasn't changed, no need to update
                return

            # Set mode (events handle audio/UI sync automatically)
            pad = self.editor.set_pad_mode(selected_pad, mode)

        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            self.notify(f"Error: {e}", severity="error")
