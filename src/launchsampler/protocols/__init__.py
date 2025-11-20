"""Protocol definitions for domain-specific observer patterns and interfaces.

This package contains protocols and events specific to the launchsampler domain:
- Events: MIDI, playback, editing, selection, and application events
- Observers: Protocols for components that react to these events

For generic model management protocols (ModelEvent, ModelObserver, PersistenceService),
see launchsampler.model_manager.protocols.
"""

from .events import MidiEvent, PlaybackEvent, EditEvent, SelectionEvent, AppEvent
from .observers import (
    MidiObserver,
    StateObserver,
    EditObserver,
    SelectionObserver,
    AppObserver,
)

__all__ = [
    # Events
    "MidiEvent",
    "PlaybackEvent",
    "EditEvent",
    "SelectionEvent",
    "AppEvent",
    # Observers
    "MidiObserver",
    "StateObserver",
    "EditObserver",
    "SelectionObserver",
    "AppObserver",
]
