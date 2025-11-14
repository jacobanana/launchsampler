"""Protocol definitions for observer patterns and interfaces."""

from enum import Enum
from typing import Protocol, runtime_checkable


class PlaybackEvent(Enum):
    """Events that can occur during sample playback."""

    PAD_TRIGGERED = "pad_triggered"  # Pad was just triggered (note on)
    PAD_PLAYING = "pad_playing"      # Pad started playing audio
    PAD_STOPPED = "pad_stopped"      # Pad was stopped (note off or interrupt)
    PAD_FINISHED = "pad_finished"    # Pad finished playing naturally


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
