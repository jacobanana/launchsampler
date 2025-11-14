"""State machine for managing sampler playback state and event dispatch."""

import logging
from threading import Lock
from typing import Optional

from launchsampler.protocols import PlaybackEvent, StateObserver

logger = logging.getLogger(__name__)


class SamplerStateMachine:
    """
    Manages playback state and dispatches events to observers.

    This class acts as the single source of truth for playback state
    and coordinates event dispatch to registered observers. It is
    thread-safe and designed to be called from the audio thread.

    The state machine tracks:
    - Which pads are currently playing
    - Which pads are triggered but not yet playing
    - Registered observers that receive events
    """

    def __init__(self) -> None:
        """Initialize the state machine."""
        self._lock = Lock()
        self._playing_pads: set[int] = set()
        self._triggered_pads: set[int] = set()
        self._observers: list[StateObserver] = []

    def register_observer(self, observer: StateObserver) -> None:
        """
        Register an observer to receive playback events.

        Args:
            observer: Object implementing StateObserver protocol
        """
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
                logger.debug(f"Registered observer: {observer}")

    def unregister_observer(self, observer: StateObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
                logger.debug(f"Unregistered observer: {observer}")

    def on_pad_triggered(self, pad_index: int) -> None:
        """
        Handle pad trigger event (note on received).

        Args:
            pad_index: Index of triggered pad
        """
        with self._lock:
            self._triggered_pads.add(pad_index)
            self._notify_observers(PlaybackEvent.PAD_TRIGGERED, pad_index)

    def on_pad_playing(self, pad_index: int) -> None:
        """
        Handle pad playing event (audio started).

        Args:
            pad_index: Index of pad that started playing
        """
        with self._lock:
            self._triggered_pads.discard(pad_index)
            self._playing_pads.add(pad_index)
            self._notify_observers(PlaybackEvent.PAD_PLAYING, pad_index)

    def on_pad_stopped(self, pad_index: int) -> None:
        """
        Handle pad stopped event (note off or interrupt).

        Args:
            pad_index: Index of pad that was stopped
        """
        with self._lock:
            was_playing = pad_index in self._playing_pads
            self._triggered_pads.discard(pad_index)
            self._playing_pads.discard(pad_index)

            if was_playing:
                self._notify_observers(PlaybackEvent.PAD_STOPPED, pad_index)

    def on_pad_finished(self, pad_index: int) -> None:
        """
        Handle pad finished event (playback completed naturally).

        Args:
            pad_index: Index of pad that finished playing
        """
        with self._lock:
            was_playing = pad_index in self._playing_pads
            self._playing_pads.discard(pad_index)

            if was_playing:
                self._notify_observers(PlaybackEvent.PAD_FINISHED, pad_index)

    def is_pad_playing(self, pad_index: int) -> bool:
        """
        Check if a pad is currently playing.

        Args:
            pad_index: Index of pad to check

        Returns:
            True if pad is playing
        """
        with self._lock:
            return pad_index in self._playing_pads

    def get_playing_pads(self) -> list[int]:
        """
        Get list of all currently playing pads.

        Returns:
            List of pad indices that are currently playing
        """
        with self._lock:
            return list(self._playing_pads)

    def _notify_observers(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Notify all registered observers of an event.

        Args:
            event: The playback event that occurred
            pad_index: Index of the pad involved

        Note:
            Must be called with lock held.
            Catches and logs exceptions from observers to prevent
            one bad observer from breaking others.
        """
        for observer in self._observers:
            try:
                observer.on_playback_event(event, pad_index)
            except Exception as e:
                logger.error(
                    f"Error notifying observer {observer} of {event.value} "
                    f"for pad {pad_index}: {e}",
                    exc_info=True
                )
