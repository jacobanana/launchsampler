"""Protocol definitions for domain-specific observer patterns and interfaces.

This module contains protocols specific to the launchsampler domain:
- MIDI events and observers
- Playback events and observers
- Edit events and observers
- Selection events and observers
- Application events and observers
- UI adapter protocol

For generic model management protocols (ModelEvent, ModelObserver, PersistenceService),
see launchsampler.model_manager.protocols.
"""

from enum import Enum
from typing import Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from launchsampler.models import Pad


class MidiEvent(Enum):
    """Events from MIDI controller input."""

    NOTE_ON = "note_on"                          # MIDI note on received
    NOTE_OFF = "note_off"                        # MIDI note off received
    CONTROL_CHANGE = "control_change"            # MIDI control change received
    CONTROLLER_CONNECTED = "controller_connected"    # MIDI controller connected
    CONTROLLER_DISCONNECTED = "controller_disconnected"  # MIDI controller disconnected


class PlaybackEvent(Enum):
    """Events from audio playback engine."""

    PAD_TRIGGERED = "pad_triggered"  # Pad was just triggered (note on)
    PAD_PLAYING = "pad_playing"      # Pad started playing audio
    PAD_STOPPED = "pad_stopped"      # Pad was stopped (note off or interrupt)
    PAD_FINISHED = "pad_finished"    # Pad finished playing naturally


class EditEvent(Enum):
    """
    Events that occur during editing operations.

    These events represent PERSISTENT state changes (saved to disk).
    For ephemeral UI state (selection), see SelectionEvent.
    """

    PAD_ASSIGNED = "pad_assigned"           # Sample assigned to pad
    PAD_CLEARED = "pad_cleared"             # Pad sample removed
    PAD_MOVED = "pad_moved"                 # Pad moved/swapped
    PAD_DUPLICATED = "pad_duplicated"       # Pad duplicated to another location
    PAD_MODE_CHANGED = "pad_mode_changed"   # Playback mode changed
    PAD_VOLUME_CHANGED = "pad_volume_changed"  # Volume changed
    PAD_NAME_CHANGED = "pad_name_changed"   # Sample name changed
    PADS_CLEARED = "pads_cleared"           # Multiple pads cleared


class SelectionEvent(Enum):
    """
    Events for pad selection changes (ephemeral UI state).

    Selection is UI-specific state that doesn't persist to disk.
    Different UIs can have independent selections.
    """

    CHANGED = "changed"        # Selection changed to a specific pad
    CLEARED = "cleared"        # Selection cleared (no pad selected)


@runtime_checkable
class MidiObserver(Protocol):
    """
    Observer that receives MIDI controller events.

    This protocol allows loose coupling between the MIDI controller
    and components that need to react to MIDI input (e.g., UI feedback).
    """

    def on_midi_event(self, event: "MidiEvent", pad_index: int, control: int = 0, value: int = 0) -> None:
        """
        Handle MIDI controller events.

        Args:
            event: The type of MIDI event
            pad_index: Index of the pad (0-63), or -1 for connection/CC events
            control: MIDI CC control number (for CONTROL_CHANGE events)
            value: MIDI CC value (for CONTROL_CHANGE events)

        Note:
            This is called from the MIDI polling thread, so implementations
            should be thread-safe and avoid blocking operations.
        """
        ...


@runtime_checkable
class StateObserver(Protocol):
    """
    Observer that receives audio playback state change events.

    This protocol allows loose coupling between the audio engine
    and UI components. Any object implementing this protocol can
    observe state changes without tight coupling.
    """

    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback state changes.

        Args:
            event: The type of playback event
            pad_index: Index of the pad that changed state (0-63)

        Note:
            This may be called from the audio thread, so implementations
            should be thread-safe and avoid blocking operations.
        """
        ...


@runtime_checkable
class EditObserver(Protocol):
    """
    Observer that receives editing events.

    This protocol allows loose coupling between the editor service
    and components that need to react to edits (audio engine, UI, etc.).
    """

    def on_edit_event(
        self,
        event: "EditEvent",
        pad_indices: list[int],
        pads: list["Pad"]
    ) -> None:
        """
        Handle editing events.

        Args:
            event: The type of editing event
            pad_indices: List of affected pad indices (0-63)
            pads: List of affected pad states (post-edit)

        Threading:
            Called from the UI thread (Textual's main asyncio loop).
            Audio-related observers (e.g., Player) must ensure their
            engine methods are thread-safe (typically via locks).

        Error Handling:
            Exceptions raised by observers are caught and logged by the
            EditorService. They do not propagate to the caller, ensuring
            one failing observer doesn't break others. Observers should
            not rely on exceptions for critical error signaling.
        """
        ...


@runtime_checkable
class SelectionObserver(Protocol):
    """
    Observer that receives selection change events.

    This protocol separates ephemeral UI state (selection) from
    persistent data mutations (edits). Selection is UI-specific and
    doesn't affect audio engine or persistence layers.
    """

    def on_selection_event(
        self,
        event: "SelectionEvent",
        pad_index: Optional[int]
    ) -> None:
        """
        Handle selection change events.

        Args:
            event: The type of selection event
            pad_index: Index of selected pad (0-63), or None if cleared

        Threading:
            Called from the UI thread (Textual's main asyncio loop).
            Implementations should be lightweight and non-blocking.
        """
        ...


class AppEvent(Enum):
    """Events from application lifecycle and state changes."""

    SET_MOUNTED = "set_mounted"      # Set was mounted into the application
    SET_SAVED = "set_saved"          # Set was saved to disk
    SET_AUTO_CREATED = "set_auto_created"  # Set was auto-created because file didn't exist
    MODE_CHANGED = "mode_changed"    # Application mode changed (sampler/arranger)


@runtime_checkable
class AppObserver(Protocol):
    """
    Observer that receives application lifecycle events.

    This protocol allows loose coupling between the application core
    and UI/service components that need to react to app-level changes.
    """

    def on_app_event(self, event: "AppEvent", **kwargs) -> None:
        """
        Handle application lifecycle events.

        Args:
            event: The type of application event
            **kwargs: Event-specific data (e.g., set_name, mode, etc.)

        Threading:
            Called from the UI thread (Textual's main asyncio loop).
            Implementations should avoid blocking operations.

        Error Handling:
            Exceptions raised by observers are caught and logged by the
            application. They do not propagate to the caller, ensuring
            one failing observer doesn't break others.
        """
        ...


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

