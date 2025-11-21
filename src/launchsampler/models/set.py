"""Set model for pad configurations (data structure only - persistence is in SetManagerService)."""

import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_serializer

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
    samples_root: Path | None = Field(
        default=None, description="Root directory for sample paths (None = relative to Set file)"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    modified_at: datetime = Field(
        default_factory=datetime.now, description="Last modified timestamp"
    )

    @field_serializer("created_at", "modified_at")
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()

    @field_serializer("samples_root")
    def serialize_samples_root(self, samples_root: Path | None) -> str | None:
        """Serialize samples_root Path to string using forward slashes for portability."""
        return samples_root.as_posix() if samples_root else None

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
            samples_dir=samples_dir, auto_configure=auto_configure, default_volume=default_volume
        )

        return cls(
            name=name,
            launchpad=launchpad,
            samples_root=samples_dir,  # Paths will be relative to this directory
        )

    @classmethod
    def create_empty(cls, name: str) -> "Set":
        """Create a new empty set."""
        return cls(name=name, launchpad=Launchpad.create_empty())
