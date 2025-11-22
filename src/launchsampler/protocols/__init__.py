"""Protocol definitions for domain-specific observer patterns and interfaces.

This package contains protocols and events specific to the launchsampler domain:
- Events: MIDI, playback, editing, selection, and application events
- Observers: Protocols for components that react to these events

For generic model management protocols (ModelEvent, ModelObserver, PersistenceService),
see launchsampler.model_manager.protocols.
"""

from .events import AppEvent, EditEvent, MidiEvent, PlaybackEvent, SelectionEvent
from .observers import (
    AppObserver,
    EditObserver,
    MidiObserver,
    SelectionObserver,
    StateObserver,
)

__all__ = [
    "AppEvent",
    "AppObserver",
    "EditEvent",
    "EditObserver",
    # Events
    "MidiEvent",
    # Observers
    "MidiObserver",
    "PlaybackEvent",
    "SelectionEvent",
    "SelectionObserver",
    "StateObserver",
]
