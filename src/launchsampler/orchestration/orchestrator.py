"""
Application orchestrator for coordinating services and UIs.

This module coordinates all services and UIs for the Launchpad Sampler application.
The design allows running headless (MIDI-only) or with TUI, and makes
it easy to add other UI implementations (web, native GUI, etc.).
"""

import logging
from pathlib import Path
from typing import Optional

from launchsampler.core.player import Player
from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.devices import DeviceController
from launchsampler.models import AppConfig, Launchpad, Set
from launchsampler.protocols import AppEvent, AppObserver
from launchsampler.ui_shared import UIAdapter
from launchsampler.services import ModelManagerService, EditorService, SetManagerService
from launchsampler.model_manager import ObserverManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Top-level orchestrator for the Launchpad Sampler application.

    Coordinates:
    - Core state (Launchpad, Set, mode)
    - Services (Player, SetManager, Editor)
    - Multiple UI implementations (TUI, LED, web, etc.)
    - Application lifecycle (initialize, run, shutdown)

    The Textual TUI is just one possible UI - you can run headless with
    just the Launchpad hardware, or add other UIs (web, native) without
    changing this orchestrator.

    Architecture:
        Orchestrator (this class)
        ├── Core State: launchpad, current_set, mode
        ├── Services: config_service, set_manager, player, editor
        └── UIs (observers): textual_ui, led_ui, etc.
    """

    def __init__(
        self,
        config: AppConfig,
        set_name: Optional[str] = None,
        samples_dir: Optional[Path] = None,
        start_mode: str = "edit",
        headless: bool = False
    ):
        """
        Initialize the orchestrator.

        Args:
            config: Application configuration
            set_name: Optional set to load on startup
            samples_dir: Optional directory to load samples from
            start_mode: Mode to start in ("edit" or "play")
            headless: If True, run without TUI (MIDI/LED only)
        """
        self.config = config
        self.headless = headless

        # Initial load parameters
        self._initial_set_name = set_name
        self._initial_samples_dir = samples_dir
        self._start_mode = start_mode

        # Core state - owned by orchestrator
        self._mode: Optional[str] = None
        self.launchpad: Launchpad = Launchpad.create_empty()
        self.current_set: Set = Set.create_empty("Untitled")

        # Shared resources - hardware and state
        self.state_machine = SamplerStateMachine()
        self.midi_controller: Optional[DeviceController] = None

        # Services (domain logic)
        self.config_service: Optional[ModelManagerService[AppConfig]] = None
        self.set_manager: Optional[SetManagerService] = None
        self.player: Optional[Player] = None
        self.editor: Optional[EditorService] = None

        # UI repository
        self._uis: list[UIAdapter] = []

        # Observers (UIs)
        self._app_observers = ObserverManager[AppObserver](observer_type_name="app")

    def register_ui(self, ui: UIAdapter) -> None:
        """
        Register a UI implementation.

        This should be called BEFORE initialize() to ensure the UI receives
        all startup events (SET_MOUNTED, MODE_CHANGED, etc.).

        The UI will be initialized and run as part of the application lifecycle.

        Args:
            ui: UI implementation to register
        """
        if ui not in self._uis:
            self._uis.append(ui)
            logger.info(f"Registered UI: {ui.__class__.__name__}")

            # If UI is also an observer, register it immediately
            # This ensures it receives startup events during initialize()
            if isinstance(ui, AppObserver):
                self.register_observer(ui)

    def initialize(self) -> None:
        """
        Initialize the application services and load initial state.

        This is called by the UI during on_mount (when Textual's event loop is running).
        At this point, UI observers are already registered and widgets exist.

        Fires startup events (SET_MOUNTED, MODE_CHANGED) that UIs will handle.
        """
        logger.info("Initializing Orchestrator services")

        # Initialize ModelManagerService for centralized config management
        config_path = Path.home() / ".launchsampler" / "config.json"
        self.config_service = ModelManagerService[AppConfig](
            AppConfig,
            self.config,
            default_path=config_path
        )
        logger.info("ModelManagerService initialized")

        self.set_manager = SetManagerService(self.config)

        # Create MIDI controller (shared resource)
        self._start_midi()

        # Inject shared state machine into Player
        self.player = Player(self.config, state_machine=self.state_machine)

        # Setup Editor and register player as edit observer (for audio sync)
        self.editor = EditorService(self.config)
        self.editor.register_observer(self.player)

        # Register Player as MIDI observer (if MIDI available)
        if self.midi_controller:
            self.midi_controller.register_observer(self.player)

        # Start player audio (must happen BEFORE loading set)
        try:
            self.player.start()
        except RuntimeError as e:
            logger.error(f"Failed to start player: {e}")
            if not self.headless:
                # In headless mode, we can't show notifications
                # Re-raise with the original error message
                raise

        # Register UIs with services (editor, MIDI, player callbacks)
        # This must happen AFTER MIDI controller is created but BEFORE loading set
        for ui in self._uis:
            # UIs should expose their observer service for edit events
            if hasattr(ui, 'register_with_services'):
                ui.register_with_services(self)

        # Load initial set (SetManagerService handles I/O)
        # Fires SET_MOUNTED event - UIs are already observing
        loaded_set, was_auto_created = self.set_manager.load_set(
            self._initial_set_name,
            self._initial_samples_dir
        )
        self.mount_set(loaded_set)

        # If set was auto-created, notify observers
        if was_auto_created:
            self._app_observers.notify(
                'on_app_event',
                AppEvent.SET_AUTO_CREATED,
                set_name=loaded_set.name
            )



        # Set initial mode - Fires MODE_CHANGED event
        self.set_mode(self._start_mode)

        logger.info("Orchestrator initialized successfully")

    def run(self) -> None:
        """
        Run all registered UIs.

        Initializes UIs first (sets up observers), then runs them.
        The orchestrator itself will be initialized by the UI during on_mount
        (when Textual's event loop is running).

        For interactive UIs (TUI), this will block until the UI exits.
        For background UIs (LED), this returns immediately.

        Note: Currently only supports ONE blocking UI. If you need multiple
        concurrent UIs, consider running them in separate threads/processes.
        """
        if not self._uis:
            logger.warning("No UIs registered - running headless")
            return

        # Initialize UIs first (sets up observers, but doesn't start orchestrator services yet)
        for ui in self._uis:
            logger.info(f"Initializing UI: {ui.__class__.__name__}")
            ui.initialize()

        # Run all UIs (TUI will block here)
        # The TUI will call orchestrator.initialize() once Textual is running (in on_mount)
        for ui in self._uis:
            logger.info(f"Running UI: {ui.__class__.__name__}")
            ui.run()

    def shutdown(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down Orchestrator")

        # Shutdown UIs
        for ui in self._uis:
            logger.info(f"Shutting down UI: {ui.__class__.__name__}")
            try:
                ui.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down UI {ui.__class__.__name__}: {e}")

        # Shutdown player
        if self.player:
            self.player.stop()

        # Shutdown MIDI controller
        self._stop_midi()

    def _start_midi(self) -> bool:
        """Start MIDI controller (shared resource)."""
        try:
            self.midi_controller = DeviceController(
                poll_interval=self.config.midi_poll_interval
            )
            self.midi_controller.start()
            logger.info("MIDI controller started")
            return True
        except Exception as e:
            logger.warning(f"MIDI not available: {e}")
            self.midi_controller = None
            return False

    def _stop_midi(self) -> None:
        """Stop MIDI controller."""
        if self.midi_controller:
            self.midi_controller.stop()
            self.midi_controller = None
            logger.info("MIDI controller stopped")

    def register_observer(self, observer: AppObserver) -> None:
        """
        Register an observer for app-level events.

        UIs should register themselves as observers to receive updates.

        Args:
            observer: The observer to register
        """
        self._app_observers.register(observer)

    def unregister_observer(self, observer: AppObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: The observer to unregister
        """
        self._app_observers.unregister(observer)

    def _notify_observers(self, event: AppEvent, **kwargs) -> None:
        """
        Notify all registered observers of an app-level event.

        Args:
            event: The app event that occurred
            **kwargs: Event-specific data
        """
        self._app_observers.notify('on_app_event', event, **kwargs)

    # =================================================================
    # Set Management
    # =================================================================

    def mount_set(self, loaded_set: Set) -> None:
        """
        Mount a set into the application.

        This activates the Set in the running application:
        - Updates orchestrator state
        - Syncs with player (audio engine)
        - Syncs with editor (launchpad reference)
        - Fires events to notify observers (UIs)

        Args:
            loaded_set: The Set to mount (already loaded from disk/directory)
        """
        # Update core state
        self.launchpad = loaded_set.launchpad
        self.current_set = Set(
            name=loaded_set.name,
            launchpad=self.launchpad,
            samples_root=loaded_set.samples_root,
            created_at=loaded_set.created_at,
            modified_at=loaded_set.modified_at
        )

        # Update editor (launchpad reference sync)
        if self.editor:
            logger.info("Updating EditorService with new launchpad reference")
            self.editor.update_launchpad(self.launchpad)
        else:
            logger.warning("EditorService not initialized - cannot update launchpad reference")

        # Update player (audio engine sync)
        if self.player.is_running:
            logger.info("Loading set into Player")
            self.player.load_set(self.current_set)
        else:
            logger.warning("Player not running - cannot load set")  

        # Notify observers (UIs will sync)
        self._notify_observers(AppEvent.SET_MOUNTED)

        logger.info(f"Mounted set: {self.current_set.name} with {len(self.launchpad.assigned_pads)} samples")

    def save_set(self, path: Path, name: Optional[str] = None) -> None:
        """
        Save the current set.

        Args:
            path: Path to save to
            name: Optional new name for the set
        """
        # Update name if changed
        if name and self.current_set.name != name:
            self.current_set = Set(
                name=name,
                launchpad=self.launchpad,
                samples_root=self.current_set.samples_root,
                created_at=self.current_set.created_at,
                modified_at=self.current_set.modified_at
            )

        # Save
        self.set_manager.save_set(self.current_set, path)

        # Notify observers
        self._notify_observers(AppEvent.SET_SAVED, path=path, set_name=self.current_set.name)

        logger.info(f"Saved set to: {path}")

    # =================================================================
    # Mode Management
    # =================================================================

    def set_mode(self, mode: str) -> bool:
        """
        Set the app mode (edit or play).

        This only affects UI state - MIDI and audio continue in both modes.

        Args:
            mode: Target mode ("edit" or "play")

        Returns:
            True if mode was set successfully
        """
        if mode not in ("edit", "play"):
            logger.error(f"Invalid mode: {mode}")
            return False

        if self._mode == mode:
            return True

        # Update mode
        self._mode = mode

        # Notify observers (UIs will update)
        self._notify_observers(AppEvent.MODE_CHANGED, mode=mode)

        logger.info(f"Switched to {mode} mode")
        return True

    @property
    def mode(self) -> Optional[str]:
        """
        Get the current app mode.

        READ-ONLY: This is a read-only property. To change the mode,
        use set_mode() which fires AppEvent.MODE_CHANGED for observers.
        """
        return self._mode

    # =================================================================
    # Read-Only State Access
    #
    # IMPORTANT: These properties provide READ-ONLY access to state.
    # UI layers should NEVER mutate this state directly.
    #
    # To modify state, use the service methods which:
    # 1. Perform the mutation
    # 2. Fire events to notify all observers
    # 3. Ensure consistency across all UIs
    #
    # Communication Rules:
    # - Mutations: UI → Service → Event → Observer → UI Update
    # - Queries: UI → orchestrator.property (read-only)
    # =================================================================

    def get_pad(self, index: int):
        """
        Get a pad by index (read-only access).

        This is a convenience method for EditorService compatibility.
        To modify pads, use EditorService methods which fire events.

        Args:
            index: Pad index (0-63)

        Returns:
            Pad at the given index
        """
        return self.launchpad.pads[index]
