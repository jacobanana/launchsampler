"""Protocol definitions for observer patterns and interfaces."""

from enum import Enum
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from launchsampler.models import Pad


class PlaybackEvent(Enum):
    """Events that can occur during sample playback."""

    NOTE_ON = "note_on"              # MIDI note on received (always fired)
    NOTE_OFF = "note_off"            # MIDI note off received (always fired)
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
    PADS_CLEARED = "pads_cleared"           # Multiple pads cleared
    SET_LOADED = "set_loaded"               # New set loaded


@runtime_checkable
class StateObserver(Protocol):
    """
    Observer that receives state change events.

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
            
        Note:
            This is called from the UI thread, so audio-related observers
            should handle thread safety appropriately.
        """
        ...
