"""Observer protocol definitions for domain-specific events.

This module contains observer protocols for the domain:
- MIDI observers: React to MIDI controller input
- State observers: React to playback state changes
- Edit observers: React to editing operations
- Selection observers: React to selection changes
- App observers: React to application lifecycle events
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from launchsampler.models import Pad

from .events import AppEvent, EditEvent, MidiEvent, PlaybackEvent, SelectionEvent


@runtime_checkable
class MidiObserver(Protocol):
    """
    Observer that receives MIDI controller events.

    This protocol allows loose coupling between the MIDI controller
    and components that need to react to MIDI input (e.g., UI feedback).
    """

    def on_midi_event(
        self, event: "MidiEvent", pad_index: int, control: int = 0, value: int = 0
    ) -> None:
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

    def on_edit_event(self, event: "EditEvent", pad_indices: list[int], pads: list["Pad"]) -> None:
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

    def on_selection_event(self, event: "SelectionEvent", pad_index: int | None) -> None:
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
