"""Pad model representing a single grid cell."""

from pydantic import BaseModel, Field

from .color import Color
from .enums import PlaybackMode
from .sample import Sample


class Pad(BaseModel):
    """Represents a single pad in the 8x8 grid."""

    x: int = Field(ge=0, lt=8, description="X coordinate (0-7)")
    y: int = Field(ge=0, lt=8, description="Y coordinate (0-7)")
    sample: Sample | None = Field(default=None, description="Assigned sample")
    color: Color = Field(default_factory=Color.off, description="LED color")
    mode: PlaybackMode = Field(default=PlaybackMode.ONE_SHOT, description="Playback mode")
    volume: float = Field(default=1.0, ge=0.0, le=1.0, description="Volume (0.0-1.0)")

    @property
    def is_assigned(self) -> bool:
        """Check if pad has a sample assigned."""
        return self.sample is not None

    def get_sample(self) -> Sample:
        """
        Get the assigned sample, raising an error if not assigned.

        Returns:
            The assigned Sample

        Raises:
            ValueError: If pad has no sample assigned

        Example:
            >>> if pad.is_assigned:
            ...     sample = pad.get_sample()  # mypy knows this returns Sample, not None
            ...     print(sample.name)
        """
        if self.sample is None:
            raise ValueError("Pad has no sample assigned")
        return self.sample

    @property
    def position(self) -> tuple[int, int]:
        """Get (x, y) position as tuple."""
        return (self.x, self.y)

    def clear(self) -> None:
        """Clear the pad (remove sample and turn off LED)."""
        self.sample = None
        self.color = Color.off()

    @classmethod
    def empty(cls, x: int, y: int) -> "Pad":
        """Create an empty pad at given position."""
        return cls(x=x, y=y)
