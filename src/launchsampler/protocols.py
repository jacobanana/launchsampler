"""Protocol definitions for observer patterns and interfaces."""

from enum import Enum
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from launchsampler.models import Pad


class MidiEvent(Enum):
    """Events from MIDI controller input."""
    
    NOTE_ON = "note_on"                          # MIDI note on received
    NOTE_OFF = "note_off"                        # MIDI note off received
    CONTROLLER_CONNECTED = "controller_connected"    # MIDI controller connected
    CONTROLLER_DISCONNECTED = "controller_disconnected"  # MIDI controller disconnected


class PlaybackEvent(Enum):
    """Events from audio playback engine."""

    PAD_TRIGGERED = "pad_triggered"  # Pad was just triggered (note on)
    PAD_PLAYING = "pad_playing"      # Pad started playing audio
    PAD_STOPPED = "pad_stopped"      # Pad was stopped (note off or interrupt)
    PAD_FINISHED = "pad_finished"    # Pad finished playing naturally


class EditEvent(Enum):
    """Events that occur during editing operations."""

    PAD_ASSIGNED = "pad_assigned"           # Sample assigned to pad
    PAD_CLEARED = "pad_cleared"             # Pad sample removed
    PAD_MOVED = "pad_moved"                 # Pad moved/swapped
    PAD_DUPLICATED = "pad_duplicated"       # Pad duplicated to another location
    PAD_MODE_CHANGED = "pad_mode_changed"   # Playback mode changed
    PAD_VOLUME_CHANGED = "pad_volume_changed"  # Volume changed
    PAD_NAME_CHANGED = "pad_name_changed"   # Sample name changed
    PAD_SELECTED = "pad_selected"           # Pad selection changed
    PADS_CLEARED = "pads_cleared"           # Multiple pads cleared


@runtime_checkable
class MidiObserver(Protocol):
    """
    Observer that receives MIDI controller events.
    
    This protocol allows loose coupling between the MIDI controller
    and components that need to react to MIDI input (e.g., UI feedback).
    """

    def on_midi_event(self, event: "MidiEvent", pad_index: int) -> None:
        """
        Handle MIDI controller events.
        
        Args:
            event: The type of MIDI event
            pad_index: Index of the pad (0-63), or -1 for connection events
            
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
