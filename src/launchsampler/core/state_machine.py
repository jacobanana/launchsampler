"""State machine for managing sampler playback state and event dispatch."""

import logging
from threading import Lock

from launchsampler.model_manager import ObserverManager
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
        # ObserverManager has its own lock - don't share to avoid deadlock when notifying while holding _lock
        self._observers = ObserverManager[StateObserver](observer_type_name="state")

    def register_observer(self, observer: StateObserver) -> None:
        """
        Register an observer to receive playback events.

        Args:
            observer: Object implementing StateObserver protocol
        """
        self._observers.register(observer)

    def unregister_observer(self, observer: StateObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        self._observers.unregister(observer)

    def notify_pad_triggered(self, pad_index: int) -> None:
        """
        Notify that a pad trigger event occurred (note on received).

        Args:
            pad_index: Index of triggered pad
        """
        with self._lock:
            self._triggered_pads.add(pad_index)
        # Notify observers AFTER releasing lock to avoid deadlock
        self._notify_observers(PlaybackEvent.PAD_TRIGGERED, pad_index)

    def notify_pad_playing(self, pad_index: int) -> None:
        """
        Notify that a pad playing event occurred (audio started).

        Args:
            pad_index: Index of pad that started playing
        """
        with self._lock:
            self._triggered_pads.discard(pad_index)
            self._playing_pads.add(pad_index)
        # Notify observers AFTER releasing lock to avoid deadlock
        self._notify_observers(PlaybackEvent.PAD_PLAYING, pad_index)

    def notify_pad_stopped(self, pad_index: int) -> None:
        """
        Notify that a pad stopped event occurred (note off or interrupt).

        Args:
            pad_index: Index of pad that was stopped
        """
        with self._lock:
            was_playing = pad_index in self._playing_pads
            self._triggered_pads.discard(pad_index)
            self._playing_pads.discard(pad_index)

        # Notify observers AFTER releasing lock to avoid deadlock
        if was_playing:
            self._notify_observers(PlaybackEvent.PAD_STOPPED, pad_index)

    def notify_pad_finished(self, pad_index: int) -> None:
        """
        Notify that a pad finished event occurred (playback completed naturally).

        Args:
            pad_index: Index of pad that finished playing
        """
        with self._lock:
            was_playing = pad_index in self._playing_pads
            self._playing_pads.discard(pad_index)

        # Notify observers AFTER releasing lock to avoid deadlock
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
            Called AFTER releasing self._lock to prevent deadlock. This allows observers
            to safely query the state machine (e.g., is_pad_playing, get_playing_pads)
            during event handling. ObserverManager handles exception catching and logging automatically.
        """
        self._observers.notify("on_playback_event", event, pad_index)
