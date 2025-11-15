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
            pad_index: Index of pad to select

        Returns:
            The selected Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

        self.selected_pad_index = pad_index
        return self.launchpad.pads[pad_index]

    def get_pad(self, pad_index: int) -> Pad:
        """
        Get a pad by index (read-only).

        Args:
            pad_index: Index of pad to get

        Returns:
            The Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

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
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

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
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

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
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

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
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume {volume} out of range (0.0-1.0)")

        pad = self.launchpad.pads[pad_index]
        pad.volume = volume

        logger.info(f"Set pad {pad_index} volume to {volume:.0%}")
        return pad

    def set_sample_name(self, pad_index: int, name: str) -> Pad:
        """
        Set the name for a pad's sample.

        Args:
            pad_index: Index of pad to modify
            name: New sample name

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad has no sample assigned or name is empty
        """
        num_pads = len(self.launchpad.pads)
        if not 0 <= pad_index < num_pads:
            raise IndexError(f"Pad index {pad_index} out of range (0-{num_pads-1})")

        if not name or not name.strip():
            raise ValueError("Sample name cannot be empty")

        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned or not pad.sample:
            raise ValueError(f"Cannot set name on empty pad {pad_index}")

        pad.sample.name = name.strip()

        logger.info(f"Set pad {pad_index} sample name to '{name}'")
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

    def move_pad(self, source_index: int, target_index: int, swap: bool = False) -> tuple[Pad, Pad]:
        """
        Move a sample from source pad to target pad.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            swap: If True, swap samples between pads. If False, overwrite target.

        Returns:
            Tuple of (new source pad, new target pad)

        Raises:
            IndexError: If pad indices are out of range
            ValueError: If source pad is empty
        """
        num_pads = len(self.launchpad.pads)
        if not 0 <= source_index < num_pads:
            raise IndexError(f"Source pad index {source_index} out of range (0-{num_pads-1})")

        if not 0 <= target_index < num_pads:
            raise IndexError(f"Target pad index {target_index} out of range (0-{num_pads-1})")

        if source_index == target_index:
            raise ValueError("Source and target pads must be different")

        source_pad = self.launchpad.pads[source_index]
        target_pad = self.launchpad.pads[target_index]
        logger.info(f"Moving sample from pad {source_index} to pad {target_index} (swap={swap})")

        if not source_pad.is_assigned:
            raise ValueError(f"Source pad {source_index} has no sample to move")

        if swap and target_pad.is_assigned:
            # Swap samples between pads
            # Store target pad data
            target_sample = target_pad.sample
            target_mode = target_pad.mode
            target_volume = target_pad.volume
            target_color = target_pad.color

            # Move source to target
            target_pad.sample = source_pad.sample
            target_pad.mode = source_pad.mode
            target_pad.volume = source_pad.volume
            target_pad.color = source_pad.color

            # Move target to source
            source_pad.sample = target_sample
            source_pad.mode = target_mode
            source_pad.volume = target_volume
            source_pad.color = target_color

            logger.info(f"Swapped pads {source_index} and {target_index}")
        else:
            # Move/overwrite: copy source to target and clear source
            target_pad.sample = source_pad.sample
            target_pad.mode = source_pad.mode
            target_pad.volume = source_pad.volume
            target_pad.color = source_pad.color

            # Clear source pad
            source_pos = (source_pad.x, source_pad.y)
            new_source = Pad.empty(source_pos[0], source_pos[1])
            self.launchpad.pads[source_index] = new_source
            source_pad = new_source

            logger.info(f"Moved sample from pad {source_index} to {target_index}")

        return (source_pad, target_pad)

    def copy_pad(self, source_index: int, target_index: int) -> Pad:
        """
        Copy a sample from source pad to target pad.

        Creates a complete deep copy of the source pad, preserving only
        the target's position. This ensures all properties are copied
        without needing to handle them individually.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad

        Returns:
            The new target Pad

        Raises:
            IndexError: If pad indices are out of range
            ValueError: If source pad is empty or indices are the same
        """
        num_pads = len(self.launchpad.pads)
        if not 0 <= source_index < num_pads:
            raise IndexError(f"Source pad index {source_index} out of range (0-{num_pads-1})")

        if not 0 <= target_index < num_pads:
            raise IndexError(f"Target pad index {target_index} out of range (0-{num_pads-1})")

        if source_index == target_index:
            raise ValueError("Source and target pads must be different")

        source_pad = self.launchpad.pads[source_index]
        target_pad = self.launchpad.pads[target_index]

        if not source_pad.is_assigned:
            raise ValueError(f"Source pad {source_index} has no sample to copy")

        # Deep copy entire source pad but preserve target position
        new_target = source_pad.model_copy(deep=True, update={'x': target_pad.x, 'y': target_pad.y})
        self.launchpad.pads[target_index] = new_target

        logger.info(f"Copied sample from pad {source_index} to pad {target_index}")
        return new_target
