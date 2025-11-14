"""Set model for saving/loading pad configurations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_serializer

from launchsampler.utils import find_common_path

from .launchpad import Launchpad

logger = logging.getLogger(__name__)


class Set(BaseModel):
    """A saved configuration of pad assignments.

    Path Handling:
    - samples_root: Optional override for where samples are located
    - If None (default): sample paths are relative to the Set JSON file location
    - If set: sample paths are relative to samples_root
    - Absolute paths are preserved as-is
    """

    name: str = Field(description="Set name")
    launchpad: Launchpad = Field(description="Launchpad configuration")
    samples_root: Optional[Path] = Field(
        default=None,
        description="Root directory for sample paths (None = relative to Set file)"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=datetime.now, description="Last modified timestamp")

    @field_serializer("created_at", "modified_at")
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()

    @field_serializer("samples_root")
    def serialize_samples_root(self, samples_root: Optional[Path]) -> Optional[str]:
        """Serialize samples_root Path to string."""
        return str(samples_root) if samples_root else None

    def get_samples_root(self, set_file_path: Path) -> Path:
        """Get the root directory for resolving relative sample paths.

        Args:
            set_file_path: Path to the Set JSON file

        Returns:
            Path: Root directory (either explicit samples_root or Set file's directory)
        """
        if self.samples_root:
            return self.samples_root
        else:
            # Default: samples are relative to the Set JSON file's directory
            return set_file_path.parent

    def save_to_file(self, path: Path) -> None:
        """Save set to JSON file, detecting common path and converting to relative paths.

        Automatically detects the most specific common parent directory of all samples
        and uses it as samples_root. All sample paths are then stored relative to this root.

        Edge case: If the common path is a child of the Set file's directory, we set
        samples_root to None and make paths relative to the Set file instead, for portability.

        Args:
            path: Path where the Set JSON will be saved
        """
        # Get the current root for resolving any existing relative paths
        current_root = self.get_samples_root(path)

        # Collect all sample paths, ensuring they're absolute
        sample_paths = []
        for pad in self.launchpad.pads:
            if pad.is_assigned and pad.sample:
                sample_path = pad.sample.path
                # If path is relative, make it absolute using current root
                if not sample_path.is_absolute():
                    sample_path = (current_root / sample_path).resolve()
                sample_paths.append(sample_path)

        # Detect common path if we have samples
        if sample_paths:
            common_path = find_common_path(sample_paths)
            if common_path:
                # Edge case: if common_path is a child of the Set file's directory,
                # use None (relative to Set file) for better portability
                set_dir = path.parent
                try:
                    # Check if common_path is under the set directory
                    common_path.relative_to(set_dir)
                    # It is a child, so use None and make paths relative to Set file
                    self.samples_root = None
                    logger.info(f"Common path {common_path} is under Set directory, using relative paths")
                except ValueError:
                    # Common path is not under set directory, use it as samples_root
                    self.samples_root = common_path
                    logger.info(f"Detected common path: {common_path}")
            else:
                # Fallback: use the set file's directory
                self.samples_root = path.parent
                logger.info(f"No common path found, using set directory: {path.parent}")
        else:
            # No samples, use set file's directory
            self.samples_root = None

        # Get the root for path conversion
        root = self.get_samples_root(path)

        # Convert all paths to be relative to the new root
        for pad in self.launchpad.pads:
            if pad.is_assigned and pad.sample:
                sample_path = pad.sample.path

                # First ensure path is absolute
                if not sample_path.is_absolute():
                    sample_path = (current_root / sample_path).resolve()

                # Then convert to relative (where possible)
                try:
                    pad.sample.path = sample_path.relative_to(root)
                    logger.debug(f"Converted to relative: {pad.sample.path}")
                except ValueError:
                    # Path is outside root, keep absolute
                    pad.sample.path = sample_path
                    logger.warning(f"Sample outside root, keeping absolute: {pad.sample.path}")

        # Update modified timestamp
        self.modified_at = datetime.now()

        path.write_text(self.model_dump_json(indent=2))
        logger.info(f"Saved set to {path}")

    @classmethod
    def load_from_file(cls, path: Path) -> "Set":
        """Load set from JSON file, resolving relative paths.

        Args:
            path: Path to the Set JSON file

        Returns:
            Set: Loaded set with resolved absolute paths
        """
        set_obj = cls.model_validate_json(path.read_text())

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

    @classmethod
    def from_sample_directory(
        cls,
        samples_dir: Path,
        name: str = "untitled",
        auto_configure: bool = True,
        default_volume: float = 0.1,
    ) -> "Set":
        """Create a Set by scanning a directory for audio samples.

        This is a convenience method that wraps Launchpad.from_sample_directory
        and creates a Set with samples_root set to the scanned directory.

        Args:
            samples_dir: Directory containing audio samples
            name: Name for the set
            auto_configure: Auto-configure mode/color based on filename conventions
            default_volume: Default volume for all pads (0.0-1.0)

        Returns:
            Set: New set with samples loaded from directory

        Raises:
            ValueError: If samples_dir doesn't exist or contains no audio files
        """
        launchpad = Launchpad.from_sample_directory(
            samples_dir=samples_dir,
            auto_configure=auto_configure,
            default_volume=default_volume
        )

        return cls(
            name=name,
            launchpad=launchpad,
            samples_root=samples_dir  # Paths will be relative to this directory
        )

    @classmethod
    def create_empty(cls, name: str) -> "Set":
        """Create a new empty set."""
        return cls(
            name=name,
            launchpad=Launchpad.create_empty()
        )
