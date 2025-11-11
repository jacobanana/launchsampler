"""Enumerations for the Launchpad sampler."""

from enum import Enum


class PlaybackMode(str, Enum):
    """Audio playback modes."""

    ONE_SHOT = "one_shot"  # Play once, stop
    LOOP = "loop"          # Loop continuously
    HOLD = "hold"          # Play while held, stop on release


class LaunchpadModel(str, Enum):
    """Supported Launchpad hardware models."""

    LAUNCHPAD_X = "launchpad_x"
    LAUNCHPAD_MINI = "launchpad_mini"
    LAUNCHPAD_PRO = "launchpad_pro"
