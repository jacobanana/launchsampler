"""LED UI adapter for Launchpad hardware display."""

import logging
from typing import TYPE_CHECKING

from launchsampler.protocols import UIAdapter
from .services import LEDService

if TYPE_CHECKING:
    from launchsampler.app import LaunchpadSamplerApp

logger = logging.getLogger(__name__)


class LaunchpadLEDUI(UIAdapter):
    """
    LED UI implementation that displays the pad grid on Launchpad hardware.

    This UI adapter implements the UIAdapter protocol and runs in the background,
    mirroring the TUI's grid state on the physical Launchpad LEDs.

    The LED UI:
    - Runs in background (non-blocking)
    - Mirrors the 8x8 grid state from the TUI
    - Shows pad assignments with configured colors
    - Shows playing pads with pulsing yellow animation
    - Automatically syncs with all state changes

    Lifecycle:
    1. __init__: Create controller and service, register as observer
    2. initialize(): Start Launchpad controller
    3. run(): Non-blocking (returns immediately)
    4. shutdown(): Stop controller and clean up
    """

    def __init__(self, orchestrator: "LaunchpadSamplerApp", poll_interval: float = 5.0):
        """
        Initialize the LED UI.

        Args:
            orchestrator: The LaunchpadSamplerApp orchestrator
            poll_interval: How often to check for Launchpad device (seconds)
        """
        self.orchestrator = orchestrator
        self.poll_interval = poll_interval

        # We'll reuse the Player's LaunchpadController instead of creating our own
        # This avoids MIDI port conflicts
        self.controller = None  # Will be set in register_with_services()

        # Create LED service (observer) - controller will be set later
        # Pass the shared state machine from orchestrator
        self.service = LEDService(None, orchestrator, orchestrator.state_machine)

        # Register service with orchestrator services
        self._register_with_services()

        logger.info("LaunchpadLEDUI initialized")

    def _register_with_services(self) -> None:
        """
        Register LED service as observer with orchestrator.

        This ensures the LED UI receives app-level events.
        Service-level registration happens later in register_with_services().
        """
        # Register with orchestrator for app events
        self.orchestrator.register_observer(self.service)
        logger.info("LED service registered as app observer")

    def initialize(self) -> None:
        """
        Initialize the LED UI before the orchestrator starts.

        The LED UI reuses the Player's LaunchpadController, so there's
        nothing to initialize here. The controller is already started by the Player.
        """
        logger.info("Initializing LED UI (reusing Player's LaunchpadController)")
        # Nothing to do - we reuse the Player's controller
        pass

    def register_with_services(self, orchestrator: "LaunchpadSamplerApp") -> None:
        """
        Register LED service with all orchestrator services after they're initialized.

        Called by orchestrator after services are created.

        Args:
            orchestrator: The LaunchpadSamplerApp instance
        """
        # Reuse the Player's LaunchpadController (avoid MIDI port conflicts)
        if orchestrator.player._midi:
            self.controller = orchestrator.player._midi
            self.service.controller = self.controller
            logger.info("LED UI reusing Player's LaunchpadController")
        else:
            logger.warning("No MIDI controller available - LED UI will not function")

        # Register with editor for edit events
        orchestrator.editor.register_observer(self.service)

        # Register for playback events (proper observer pattern)
        orchestrator.player.register_state_observer(self.service)

        # Register as MIDI observer to receive connection events only
        # (we ignore NOTE_ON/NOTE_OFF events in on_midi_event)
        if orchestrator.player._midi:
            orchestrator.player._midi.register_observer(self.service)
            logger.info("LED service registered for MIDI connection events")

        logger.info("LED service registered with all services")

    def run(self) -> None:
        """
        Run the LED UI.

        LED UI is a background UI, so this returns immediately.
        The Launchpad controller runs in its own polling thread.
        """
        logger.info("LED UI running in background")
        # Non-blocking - LED controller runs in background thread
        pass

    def shutdown(self) -> None:
        """
        Shutdown the LED UI and clean up resources.

        Since we reuse the Player's LaunchpadController, we don't stop it here.
        We only unregister our observers.
        """
        logger.info("Shutting down LED UI")

        # Unregister observers
        try:
            self.orchestrator.unregister_observer(self.service)
            if self.orchestrator.editor:
                self.orchestrator.editor.unregister_observer(self.service)
            if self.orchestrator.player:
                self.orchestrator.player.unregister_state_observer(self.service)
                # Unregister from MIDI controller if available
                if self.orchestrator.player._midi:
                    self.orchestrator.player._midi.unregister_observer(self.service)
            logger.info("LED service unregistered from all services")
        except Exception as e:
            logger.error(f"Error unregistering LED service observers: {e}")

        # Don't stop the controller - we don't own it, the Player does
        logger.info("LED UI shut down")
