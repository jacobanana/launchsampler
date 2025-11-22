"""Enumerations for the Launchpad sampler."""

from enum import Enum


class PlaybackMode(str, Enum):
    """Audio playback modes."""

    ONE_SHOT = "one_shot"  # Play from start on each note_on, plays to end
    TOGGLE = "toggle"  # Toggle playback on/off with note_on
    HOLD = "hold"  # Play once while note held, stop on note_off
    LOOP = "loop"  # Loop continuously, restart on note_on
    LOOP_TOGGLE = "loop_toggle"  # Toggle looping on/off with note_on
