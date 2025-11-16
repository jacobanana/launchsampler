"""Service for managing set persistence and loading."""

import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from launchsampler.models import Set
from launchsampler.models.config import AppConfig
from launchsampler.utils import find_common_path

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

    def _load_set_from_file(self, path: Path) -> Set:
        """
        Load set from JSON file, resolving relative paths.

        This is the internal implementation of Set persistence.

        Args:
            path: Path to the Set JSON file

        Returns:
            Set: Loaded set with resolved absolute paths
        """
        set_obj = Set.model_validate_json(path.read_text())

        # Get the root for path resolution
        root = set_obj.get_samples_root(path)
        logger.debug(f"Resolving paths relative to: {root}")
        logger.debug(f"samples_root from file: {set_obj.samples_root}")

        # Resolve all relative paths to absolute
        for pad in set_obj.launchpad.pads:
            if pad.is_assigned and pad.sample:
                original_path = pad.sample.path
                logger.debug(f"Processing sample: {original_path} (is_absolute: {pad.sample.path.is_absolute()})")

                if not pad.sample.path.is_absolute():
                    pad.sample.path = root / pad.sample.path
                    logger.debug(f"Resolved {original_path} -> {pad.sample.path}")
                else:
                    logger.warning(f"Sample path already absolute, not resolving: {pad.sample.path}")

        logger.info(f"Loaded set from {path}")
        return set_obj

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
            set_obj = self._load_set_from_file(path)
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

    def _save_set_to_file(self, set_obj: Set, path: Path) -> Set:
        """
        Save set to JSON file, detecting common path and converting to relative paths.

        This is the internal implementation of Set persistence.

        Automatically detects the most specific common parent directory of all samples
        and uses it as samples_root. All sample paths are then stored relative to this root.

        Edge case: If the common path is a child of the Set file's directory, we set
        samples_root to None and make paths relative to the Set file instead, for portability.

        This method does NOT mutate the in-memory paths - they remain absolute for continued use.

        Args:
            set_obj: The Set object to save
            path: Path where the Set JSON will be saved

        Returns:
            The saved Set object (with updated modified_at and samples_root)
        """
        # Get the current root for resolving any existing relative paths
        current_root = set_obj.get_samples_root(path)

        # Collect all sample paths, ensuring they're absolute
        # Map: pad_index -> absolute_path
        absolute_paths_map = {}
        for idx, pad in enumerate(set_obj.launchpad.pads):
            if pad.is_assigned and pad.sample:
                sample_path = pad.sample.path
                # If path is relative, make it absolute using current root
                if not sample_path.is_absolute():
                    sample_path = (current_root / sample_path).resolve()
                absolute_paths_map[idx] = sample_path

        # Determine the samples_root to use for saving
        new_samples_root = None
        if absolute_paths_map:
            common_path = find_common_path(list(absolute_paths_map.values()))
            if common_path:
                # Edge case: if common_path is a child of the Set file's directory,
                # use None (relative to Set file) for better portability
                set_dir = path.parent
                try:
                    # Check if common_path is under the set directory
                    common_path.relative_to(set_dir)
                    # It is a child, so use None and make paths relative to Set file
                    new_samples_root = None
                    logger.info(f"Common path {common_path} is under Set directory, using relative paths")
                except ValueError:
                    # Common path is not under set directory, use it as samples_root
                    new_samples_root = common_path
                    logger.info(f"Detected common path: {common_path}")
            else:
                # Fallback: use the set file's directory
                new_samples_root = path.parent
                logger.info(f"No common path found, using set directory: {path.parent}")

        # Create a deep copy for serialization to avoid mutating the in-memory object
        set_copy = copy.deepcopy(set_obj)

        # Update samples_root in the copy
        set_copy.samples_root = new_samples_root

        # Get the root for path conversion from the copy
        root = set_copy.get_samples_root(path)

        # Convert all paths to be relative to the new root in the COPY
        for idx, pad in enumerate(set_copy.launchpad.pads):
            if idx in absolute_paths_map:
                sample_path = absolute_paths_map[idx]

                # Convert to relative (where possible)
                try:
                    pad.sample.path = sample_path.relative_to(root)
                    logger.debug(f"Converted to relative: {pad.sample.path}")
                except ValueError:
                    # Path is outside root, keep absolute
                    pad.sample.path = sample_path
                    logger.warning(f"Sample outside root, keeping absolute: {pad.sample.path}")

        # Update modified timestamp in the copy
        set_copy.modified_at = datetime.now()

        # Save the copy, not the original
        path.write_text(set_copy.model_dump_json(indent=2))
        logger.info(f"Saved set to {path}")

        # Create updated set with new timestamp and samples_root
        updated_set = Set(
            name=set_obj.name,
            launchpad=set_obj.launchpad,
            samples_root=new_samples_root,
            created_at=set_obj.created_at,
            modified_at=set_copy.modified_at
        )

        return updated_set

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

            # Save the set (using internal implementation)
            saved_set = self._save_set_to_file(set_obj, path)

            logger.info(f"Saved set '{saved_set.name}' to {path}")
            return saved_set
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
