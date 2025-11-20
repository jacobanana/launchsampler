"""UI adapter protocol for multiple UI implementations.

This module defines the UIAdapter protocol that allows the orchestrator
to manage multiple UI implementations (TUI, LED hardware, web UI, etc.)
with a consistent lifecycle.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class UIAdapter(Protocol):
    """
    Protocol for UI implementations that can be managed by the orchestrator.

    This protocol allows the orchestrator to manage multiple UI implementations
    (TUI, LED hardware, web UI, etc.) with a consistent lifecycle.

    The orchestrator will:
    1. Register UIs before initialization (ensuring observers are connected)
    2. Initialize services and state (UIs receive all startup events)
    3. Run UIs (may block for interactive UIs like TUI)
    4. Shutdown UIs on exit

    UI implementations should:
    - Register themselves as observers in __init__
    - Initialize their widgets/components in initialize()
    - Block in run() if interactive (TUI), or return immediately if background (LED)
    - Clean up resources in shutdown()
    """

    def initialize(self) -> None:
        """
        Initialize the UI before the orchestrator starts.

        This is called BEFORE the orchestrator fires startup events,
        so UIs can set up their observer connections and widgets.

        For Textual UIs, this might create the app instance but not call run().
        For hardware UIs (LED), this might initialize GPIO or device connections.
        """
        ...

    def run(self) -> None:
        """
        Run the UI.

        For interactive UIs (TUI): This should block until the UI exits.
        For background UIs (LED): This can return immediately after starting.

        The orchestrator will call this after initialization and startup events.
        """
        ...

    def shutdown(self) -> None:
        """
        Shutdown the UI and clean up resources.

        Called when the application is exiting. UIs should:
        - Unregister observers
        - Close connections
        - Release resources
        """
        ...
