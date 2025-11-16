"""Service for managing set persistence and loading."""

import logging
from pathlib import Path
from typing import Optional

from launchsampler.models import Set
from launchsampler.models.config import AppConfig

logger = logging.getLogger(__name__)


class SetManagerService:
    """
    Handles set persistence and creation operations.

    This service is responsible for:
    - Opening existing sets from files
    - Creating new sets from sample directories
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

    def open_set(self, path: Path) -> Set:
        """
        Open an existing set from a JSON file.

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
            logger.info(f"Opened set '{set_obj.name}' from {path}")
            return set_obj
        except Exception as e:
            logger.error(f"Error opening set from {path}: {e}")
            raise ValueError(f"Failed to open set: {e}") from e

    def open_set_by_name(self, name: str) -> Optional[Set]:
        """
        Open an existing set by name from the configured sets directory.

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
            return self.open_set(set_path)
        except ValueError as e:
            logger.error(f"Error opening set '{name}': {e}")
            return None

    def create_from_directory(self, samples_dir: Path, name: Optional[str] = None) -> Set:
        """
        Create a new set from samples in a directory.

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
                f"Created set '{set_name}' with {len(set_obj.launchpad.assigned_pads)} "
                f"samples from {samples_dir}"
            )
            return set_obj
        except Exception as e:
            logger.error(f"Error creating set from {samples_dir}: {e}")
            raise ValueError(f"Failed to create set from directory: {e}") from e

    def save_set(
        self,
        set_obj: Set,
        path: Path,
        new_name: Optional[str] = None
    ) -> Set:
        """
        Save a set to a JSON file.

        Args:
            set_obj: The Set object to save
            path: Path where the set should be saved (.json)
            new_name: Optional new name for the set

        Returns:
            The saved Set object (with updated name if provided)

        Raises:
            ValueError: If save operation fails
        """
        try:
            # Update name if provided
            if new_name and set_obj.name != new_name:
                set_obj = Set(
                    name=new_name,
                    launchpad=set_obj.launchpad,
                    samples_root=set_obj.samples_root,
                    created_at=set_obj.created_at,
                    modified_at=set_obj.modified_at
                )

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Save the set
            set_obj.save_to_file(path)

            logger.info(f"Saved set '{set_obj.name}' to {path}")
            return set_obj
        except Exception as e:
            logger.error(f"Error saving set to {path}: {e}")
            raise ValueError(f"Failed to save set: {e}") from e

    def save_set_to_library(
        self,
        set_obj: Set,
        filename: Optional[str] = None
    ) -> tuple[Set, Path]:
        """
        Save a set to the configured sets library directory.

        Args:
            set_obj: The Set object to save
            filename: Optional filename (without .json extension).
                     Defaults to set_obj.name

        Returns:
            Tuple of (saved Set object, path where it was saved)

        Raises:
            ValueError: If save operation fails
        """
        name = filename or set_obj.name
        set_path = self.config.sets_dir / f"{name}.json"

        saved_set = self.save_set(set_obj, set_path)
        return saved_set, set_path

    def create_empty(self, name: str = "Untitled") -> Set:
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

    def load_set(
        self,
        set_name: Optional[str] = None,
        samples_dir: Optional[Path] = None
    ) -> Set:
        """
        Load a set with smart fallback logic.

        This handles the I/O operation of loading a Set from various sources
        (disk, directory, or creating empty). The returned Set object can then
        be mounted into the application.

        Priority order:
        1. Load from samples directory (if provided)
        2. Load from saved set file by name
        3. Create empty set as fallback

        Args:
            set_name: Name of set to load (defaults to "Untitled")
            samples_dir: Directory to load samples from (highest priority)

        Returns:
            Loaded or created Set object
        """
        name = set_name or "Untitled"

        # Priority 1: Load from samples directory
        if samples_dir:
            try:
                loaded_set = self.create_from_directory(samples_dir, name)
                logger.info(f"Loaded initial set from samples directory: {samples_dir}")
                return loaded_set
            except ValueError as e:
                logger.error(f"Failed to load from samples directory: {e}")
                # Fall through to next priority

        # Priority 2: Load from saved set file
        if name and name.lower() != "untitled":
            loaded_set = self.open_set_by_name(name)
            if loaded_set:
                logger.info(f"Loaded initial set from saved file: {name}")
                return loaded_set
            else:
                logger.warning(f"Set '{name}' not found, creating empty set")

        # Fallback: empty set
        logger.info(f"Creating empty set '{name}'")
        return self.create_empty(name)
