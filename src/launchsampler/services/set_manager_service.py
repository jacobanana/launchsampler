"""Service for managing set persistence and loading."""

import logging
from pathlib import Path
from typing import Optional

from launchsampler.models import Set
from launchsampler.models.config import AppConfig

logger = logging.getLogger(__name__)


class SetManagerService:
    """
    Handles set persistence and loading operations.

    This service is responsible for:
    - Loading sets from files
    - Loading sets from sample directories
    - Saving sets to files
    - Managing set file paths and naming

    The service is stateless - it operates on Set objects passed to it
    and returns new Set objects, without storing any state internally.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the SetManagerService.

        Args:
            config: Application configuration
        """
        self.config = config

    def load_from_file(self, path: Path) -> Set:
        """
        Load a set from a JSON file.

        Args:
            path: Path to the set file (.json)

        Returns:
            Loaded Set object

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is invalid or corrupted
        """
        if not path.exists():
            raise FileNotFoundError(f"Set file not found: {path}")

        try:
            set_obj = Set.load_from_file(path)
            logger.info(f"Loaded set '{set_obj.name}' from {path}")
            return set_obj
        except Exception as e:
            logger.error(f"Error loading set from {path}: {e}")
            raise ValueError(f"Failed to load set: {e}") from e

    def load_from_file_by_name(self, name: str) -> Optional[Set]:
        """
        Load a set by name from the configured sets directory.

        Args:
            name: Name of the set (without .json extension)

        Returns:
            Loaded Set object, or None if not found or error occurred
        """
        set_path = self.config.sets_dir / f"{name}.json"

        if not set_path.exists():
            logger.warning(f"Set file not found: {set_path}")
            return None

        try:
            return self.load_from_file(set_path)
        except ValueError as e:
            logger.error(f"Error loading set '{name}': {e}")
            return None

    def load_from_directory(self, samples_dir: Path, name: Optional[str] = None) -> Set:
        """
        Load samples from a directory and create a new set.

        Scans the directory for supported audio files and creates a set
        with samples auto-assigned to pads.

        Args:
            samples_dir: Directory containing sample files
            name: Optional name for the set (defaults to directory name)

        Returns:
            New Set object with samples loaded

        Raises:
            ValueError: If directory doesn't exist or contains no valid samples
        """
        if not samples_dir.exists() or not samples_dir.is_dir():
            raise ValueError(f"Invalid samples directory: {samples_dir}")

        set_name = name or samples_dir.name

        try:
            set_obj = Set.from_sample_directory(
                samples_dir=samples_dir,
                name=set_name,
                auto_configure=True
            )
            logger.info(
                f"Loaded set '{set_name}' with {len(set_obj.launchpad.assigned_pads)} "
                f"samples from {samples_dir}"
            )
            return set_obj
        except Exception as e:
            logger.error(f"Error loading samples from {samples_dir}: {e}")
            raise ValueError(f"Failed to load samples: {e}") from e

    def save_to_file(self, set_obj: Set, path: Path) -> None:
        """
        Save a set to a JSON file.

        Args:
            set_obj: The Set object to save
            path: Path where the set should be saved (.json)

        Raises:
            ValueError: If save operation fails
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Save the set
            set_obj.save_to_file(path)

            logger.info(f"Saved set '{set_obj.name}' to {path}")
        except Exception as e:
            logger.error(f"Error saving set to {path}: {e}")
            raise ValueError(f"Failed to save set: {e}") from e

    def save_to_sets_directory(self, set_obj: Set, filename: Optional[str] = None) -> Path:
        """
        Save a set to the configured sets directory.

        Args:
            set_obj: The Set object to save
            filename: Optional filename (without .json extension).
                     Defaults to set_obj.name

        Returns:
            Path where the set was saved

        Raises:
            ValueError: If save operation fails
        """
        name = filename or set_obj.name
        set_path = self.config.sets_dir / f"{name}.json"

        self.save_to_file(set_obj, set_path)
        return set_path

    def create_empty_set(self, name: str = "Untitled") -> Set:
        """
        Create a new empty set.

        Args:
            name: Name for the new set

        Returns:
            New empty Set object
        """
        set_obj = Set.create_empty(name)
        logger.info(f"Created empty set '{name}'")
        return set_obj
