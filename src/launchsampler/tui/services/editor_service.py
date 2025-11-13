"""Editor service for managing Launchpad editing operations."""

import logging
from pathlib import Path
from typing import Optional

from launchsampler.models import Launchpad, Pad, Sample, Set, AppConfig, PlaybackMode

logger = logging.getLogger(__name__)


class EditorService:
    """
    Manages editing operations on a Launchpad configuration.

    This service encapsulates all business logic for editing pads,
    managing samples, and saving/loading sets. It operates on models
    and is UI-agnostic.
    """

    def __init__(self, launchpad: Launchpad, config: AppConfig):
        """
        Initialize the editor service.

        Args:
            launchpad: The Launchpad model to edit
            config: Application configuration
        """
        self.launchpad = launchpad
        self.config = config
        self.selected_pad_index: Optional[int] = None

    def select_pad(self, pad_index: int) -> Pad:
        """
        Select a pad and return its state.

        Args:
            pad_index: Index of pad to select (0-63)

        Returns:
            The selected Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        if not 0 <= pad_index < 64:
            raise IndexError(f"Pad index {pad_index} out of range (0-63)")

        self.selected_pad_index = pad_index
        return self.launchpad.pads[pad_index]

    def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
        """
        Assign a sample to a pad.

        Args:
            pad_index: Index of pad to assign to
            sample_path: Path to audio file

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If sample file doesn't exist
        """
        if not 0 <= pad_index < 64:
            raise IndexError(f"Pad index {pad_index} out of range (0-63)")

        if not sample_path.exists():
            raise ValueError(f"Sample file not found: {sample_path}")

        # Create sample from file
        sample = Sample.from_file(sample_path)

        # Get pad and assign sample
        pad = self.launchpad.pads[pad_index]
        pad.sample = sample
        pad.volume = 0.8  # Default volume

        # Set default mode if not already configured
        if pad.mode is None:
            pad.mode = PlaybackMode.ONE_SHOT
            pad.color = pad.mode.get_default_color()

        logger.info(f"Assigned sample '{sample.name}' to pad {pad_index}")
        return pad

    def clear_pad(self, pad_index: int) -> Pad:
        """
        Clear a pad (remove sample).

        Args:
            pad_index: Index of pad to clear

        Returns:
            The new empty Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        if not 0 <= pad_index < 64:
            raise IndexError(f"Pad index {pad_index} out of range (0-63)")

        # Get current pad position
        old_pad = self.launchpad.pads[pad_index]

        # Replace with empty pad
        new_pad = Pad.empty(old_pad.x, old_pad.y)
        self.launchpad.pads[pad_index] = new_pad

        logger.info(f"Cleared pad {pad_index}")
        return new_pad

    def set_pad_mode(self, pad_index: int, mode: PlaybackMode) -> Pad:
        """
        Change the playback mode for a pad.

        Args:
            pad_index: Index of pad to modify
            mode: New playback mode

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad has no sample assigned
        """
        if not 0 <= pad_index < 64:
            raise IndexError(f"Pad index {pad_index} out of range (0-63)")

        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned:
            raise ValueError(f"Cannot set mode on empty pad {pad_index}")

        pad.mode = mode
        pad.color = mode.get_default_color()

        logger.info(f"Set pad {pad_index} mode to {mode.value}")
        return pad

    def set_pad_volume(self, pad_index: int, volume: float) -> Pad:
        """
        Set the volume for a pad.

        Args:
            pad_index: Index of pad to modify
            volume: New volume (0.0-1.0)

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If volume is out of range
        """
        if not 0 <= pad_index < 64:
            raise IndexError(f"Pad index {pad_index} out of range (0-63)")

        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume {volume} out of range (0.0-1.0)")

        pad = self.launchpad.pads[pad_index]
        pad.volume = volume

        logger.info(f"Set pad {pad_index} volume to {volume:.0%}")
        return pad

    def save_set(self, name: str) -> Path:
        """
        Save current launchpad configuration as a set.

        Args:
            name: Name for the set (without .json extension)

        Returns:
            Path to saved file

        Raises:
            ValueError: If name is empty
        """
        if not name or not name.strip():
            raise ValueError("Set name cannot be empty")

        name = name.strip()

        # Ensure sets directory exists
        self.config.ensure_directories()

        # Create Set object
        set_obj = Set(name=name, launchpad=self.launchpad)

        # Save to file
        set_path = self.config.sets_dir / f"{name}.json"
        set_obj.save_to_file(set_path)

        logger.info(f"Saved set '{name}' to {set_path}")
        return set_path

    def load_set(self, set_path: Path) -> Set:
        """
        Load a set from disk.

        Args:
            set_path: Path to set file

        Returns:
            Loaded Set object

        Raises:
            FileNotFoundError: If set file doesn't exist
        """
        if not set_path.exists():
            raise FileNotFoundError(f"Set not found: {set_path}")

        set_obj = Set.load_from_file(set_path)
        self.launchpad = set_obj.launchpad

        logger.info(f"Loaded set '{set_obj.name}' from {set_path}")
        return set_obj
