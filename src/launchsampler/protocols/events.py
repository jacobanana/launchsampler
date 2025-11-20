"""Domain events for observer pattern.

This module defines events that can occur within the application:
- MIDI events: Controller input events
- Playback events: Audio playback state changes
- Edit events: Persistent data mutations
- Selection events: Ephemeral UI state changes
- Application events: Lifecycle and state changes
"""

from enum import Enum


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


class AppEvent(Enum):
    """Events from application lifecycle and state changes."""

    SET_MOUNTED = "set_mounted"      # Set was mounted into the application
    SET_SAVED = "set_saved"          # Set was saved to disk
    SET_AUTO_CREATED = "set_auto_created"  # Set was auto-created because file didn't exist
    MODE_CHANGED = "mode_changed"    # Application mode changed (sampler/arranger)
