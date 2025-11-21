"""Launchpad model representing the 8x8 grid."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from launchsampler.ui_shared import MODE_COLORS

from .enums import PlaybackMode
from .pad import Pad
from .sample import Sample

logger = logging.getLogger(__name__)


# Constants defined at module level for use in default_factory
GRID_SIZE = 8
TOTAL_PADS = 64


def _create_default_pads() -> list[Pad]:
    """Create default 8x8 grid of pads."""
    return [Pad(x=x, y=y) for y in range(GRID_SIZE) for x in range(GRID_SIZE)]


class Launchpad(BaseModel):
    """Represents the complete 8x8 grid of pads."""

    GRID_SIZE: int = GRID_SIZE  # 8x8 grid
    TOTAL_PADS: int = TOTAL_PADS  # 8 * 8

    pads: list[Pad] = Field(
        default_factory=_create_default_pads, description="8x8 grid of pads (64 total)"
    )

    @field_validator("pads")
    @classmethod
    def validate_pad_count(cls, v: list[Pad]) -> list[Pad]:
        """Ensure exactly 64 pads."""
        if len(v) != TOTAL_PADS:
            raise ValueError(
                f"Launchpad must have exactly {TOTAL_PADS} pads ({GRID_SIZE}x{GRID_SIZE})"
            )
        return v

    def xy_to_note(self, x: int, y: int) -> int:
        """Convert (x, y) coordinates to MIDI note."""
        return y * self.GRID_SIZE + x

    def note_to_xy(self, note: int) -> tuple[int, int]:
        """Convert MIDI note to (x, y) coordinates."""
        y = note // self.GRID_SIZE
        x = note % self.GRID_SIZE
        return (x, y)

    def get_pad(self, x: int, y: int) -> Pad:
        """Get pad at specific coordinates."""
        if not (0 <= x < self.GRID_SIZE and 0 <= y < self.GRID_SIZE):
            raise ValueError(f"Invalid coordinates: ({x}, {y}). Must be 0-{self.GRID_SIZE - 1}.")
        return self.pads[self.xy_to_note(x, y)]

    def get_pad_by_note(self, note: int) -> Pad | None:
        """Get pad by MIDI note number (0-63)."""
        if not 0 <= note < self.TOTAL_PADS:
            return None
        x, y = self.note_to_xy(note)
        return self.get_pad(x, y)

    def clear_all(self) -> None:
        """Clear all pads."""
        for pad in self.pads:
            pad.clear()

    @property
    def assigned_pads(self) -> list[Pad]:
        """Get all pads that have samples assigned."""
        return [pad for pad in self.pads if pad.is_assigned]

    @classmethod
    def create_empty(cls) -> "Launchpad":
        """Create a new empty Launchpad."""
        return cls()

    @classmethod
    def from_sample_directory(
        cls,
        samples_dir: Path,
        auto_configure: bool = True,
        default_volume: float = 0.1,
    ) -> "Launchpad":
        """Create Launchpad configuration by scanning a directory for audio samples.

        Discovers audio files (WAV, MP3, FLAC) and assigns them to pads.
        If auto_configure is True, infers playback mode and color from filename.

        Args:
            samples_dir: Directory containing audio samples
            auto_configure: Auto-configure mode/color based on filename conventions
            default_volume: Default volume for all pads (0.0-1.0)

        Returns:
            Launchpad: Configured Launchpad instance

        Raises:
            ValueError: If samples_dir doesn't exist or contains no audio files
        """
        if not samples_dir.exists():
            raise ValueError(f"Samples directory not found: {samples_dir}")

        # Discover audio files recursively
        extensions = ["**/*.wav", "**/*.mp3", "**/*.flac", "**/*.ogg", "**/*.aiff"]
        sample_files = []
        for ext in extensions:
            sample_files.extend(samples_dir.glob(ext))

        if not sample_files:
            raise ValueError(f"No audio files found in {samples_dir}")

        # Sort for consistent ordering
        sample_files.sort()

        # Create empty launchpad
        launchpad = cls.create_empty()

        # Assign samples to pads (max 64)
        for i, sample_file in enumerate(sample_files[:TOTAL_PADS]):
            sample = Sample.from_file(sample_file)
            pad = launchpad.pads[i]

            # Assign sample
            pad.sample = sample
            pad.volume = default_volume

            # Auto-configure mode and color if requested
            if auto_configure:
                pad.mode = cls._infer_playback_mode(sample)
                pad.color = MODE_COLORS[pad.mode].rgb
            else:
                # Use defaults from Pad model
                pad.mode = PlaybackMode.ONE_SHOT
                pad.color = MODE_COLORS[pad.mode].rgb

            logger.debug(
                f"Pad {i}: {sample.name} ({pad.mode.value}, "
                f"RGB={pad.color.r},{pad.color.g},{pad.color.b})"
            )

        logger.info(f"Loaded {len(sample_files[:TOTAL_PADS])} samples from {samples_dir}")

        return launchpad

    @staticmethod
    def _infer_playback_mode(sample: Sample) -> PlaybackMode:
        """Infer playback mode from sample filename.

        Convention:
            - "loop" or "tone" in name → LOOP mode
            - "hold" in name → HOLD mode
            - Otherwise → ONE_SHOT mode

        Args:
            sample: Sample to analyze

        Returns:
            PlaybackMode: Inferred playback mode
        """
        name_lower = sample.name.lower()

        if "tone" in name_lower or "loop" in name_lower:
            return PlaybackMode.LOOP
        elif "hold" in name_lower:
            return PlaybackMode.HOLD
        else:
            return PlaybackMode.ONE_SHOT
