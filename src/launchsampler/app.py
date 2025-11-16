"""
Top-level Launchpad Sampler Application Orchestrator.

This is the main entry point that coordinates all services and UIs.
The design allows running headless (MIDI-only) or with TUI, and makes
it easy to add other UI implementations (web, native GUI, etc.).
"""

import logging
from pathlib import Path
from typing import Optional

from launchsampler.core.player import Player
from launchsampler.models import AppConfig, Launchpad, Set
from launchsampler.protocols import AppEvent, AppObserver
from launchsampler.services import SetManagerService
from launchsampler.tui.services import EditorService

logger = logging.getLogger(__name__)


class LaunchpadSamplerApp:
    """
    Top-level orchestrator for the Launchpad Sampler application.

    This orchestrator:
    - Owns core state (Launchpad, Set, mode)
    - Manages services (Player, SetManager, Editor)
    - Coordinates UIs (TextualUI, LaunchpadController as LED UI)
    - Fires app-level events that UIs observe

    The Textual TUI is just one possible UI - you can run headless with
    just the Launchpad hardware, or add other UIs (web, native) without
    changing this orchestrator.

    Architecture:
        LaunchpadSamplerApp (this class)
        ├── Core State: launchpad, current_set, mode
        ├── Services: player, set_manager, editor
        └── UIs (observers): textual_ui, led_ui (future)
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

        # Core state - owned by orchestrator
        self._mode: Optional[str] = None
        self.launchpad: Launchpad = Launchpad.create_empty()
        self.current_set: Set = Set.create_empty("Untitled")

        # Initial load parameters
        self._initial_set_name = set_name
        self._initial_samples_dir = samples_dir
        self._start_mode = start_mode

        # Services (domain logic)
        self.set_manager = SetManagerService(config)
        self.player = Player(config)
        self.editor = EditorService(self.launchpad, config)

        # Observers (UIs)
        self._app_observers: list[AppObserver] = []

    def initialize(self) -> None:
        """
        Initialize the application.

        This should be called after construction to set up services and load initial state.
        """
        # Load initial set
        self._load_initial_set(self._initial_set_name, self._initial_samples_dir)

        # Start player
        if not self.player.start(initial_set=self.current_set):
            logger.error("Failed to start player")
            if not self.headless:
                # In headless mode, we can't show notifications
                raise RuntimeError("Failed to start player")

        # Register player as edit observer (for audio sync)
        self.editor.register_observer(self.player)

        # Set initial mode
        self.set_mode(self._start_mode)

        logger.info("LaunchpadSamplerApp initialized")

    def shutdown(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down LaunchpadSamplerApp")
        self.player.stop()

    def register_observer(self, observer: AppObserver) -> None:
        """
        Register an observer for app-level events.

        UIs should register themselves as observers to receive updates.

        Args:
            observer: The observer to register
        """
        if observer not in self._app_observers:
            self._app_observers.append(observer)
            logger.debug(f"Registered app observer: {observer}")

    def unregister_observer(self, observer: AppObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: The observer to unregister
        """
        if observer in self._app_observers:
            self._app_observers.remove(observer)
            logger.debug(f"Unregistered app observer: {observer}")

    def _notify_observers(self, event: AppEvent, **kwargs) -> None:
        """
        Notify all registered observers of an app-level event.

        Args:
            event: The app event that occurred
            **kwargs: Event-specific data
        """
        for observer in self._app_observers:
            try:
                observer.on_app_event(event, **kwargs)
            except Exception as e:
                logger.error(f"Error notifying observer {observer} of {event}: {e}")

    # =================================================================
    # Set Management
    # =================================================================

    def load_set(self, loaded_set: Set) -> None:
        """
        Load a new set.

        This is the single point of truth for loading sets.

        Args:
            loaded_set: The Set to load
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

        # Update player
        if self.player.is_running:
            self.player.load_set(self.current_set)

        # Notify observers (UIs will sync)
        self._notify_observers(AppEvent.SET_LOADED)

        logger.info(f"Loaded set: {self.current_set.name} with {len(self.launchpad.assigned_pads)} samples")

    def _load_initial_set(self, set_name: Optional[str], samples_dir: Optional[Path]) -> None:
        """
        Load initial set configuration.

        Args:
            set_name: Name of set to load
            samples_dir: Directory to load samples from
        """
        name = set_name or "Untitled"

        try:
            # Priority 1: Load from samples directory
            if samples_dir:
                loaded_set = self.set_manager.create_from_directory(samples_dir, name)
                self.load_set(loaded_set)
                return

            # Priority 2: Load from saved set file
            if name and name.lower() != "untitled":
                loaded_set = self.set_manager.open_set_by_name(name)
                if loaded_set:
                    self.load_set(loaded_set)
                    return
                else:
                    logger.warning(f"Set '{name}' not found, creating empty set")

            # Fallback: empty set
            logger.info(f"Created empty set '{name}'")
            self.current_set = Set.create_empty(name)
            self.current_set.launchpad = self.launchpad

        except Exception as e:
            logger.error(f"Error loading initial set: {e}")
            raise

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
