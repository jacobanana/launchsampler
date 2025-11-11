"""Launchpad model representing the 8x8 grid."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import LaunchpadModel
from .pad import Pad


class Launchpad(BaseModel):
    """Represents the complete 8x8 grid of pads."""

    model: LaunchpadModel = Field(
        default=LaunchpadModel.LAUNCHPAD_X,
        description="Launchpad hardware model"
    )
    pads: list[Pad] = Field(
        default_factory=lambda: [
            Pad(x=x, y=y) for y in range(8) for x in range(8)
        ],
        description="8x8 grid of pads (64 total)"
    )

    @field_validator("pads")
    @classmethod
    def validate_pad_count(cls, v: list[Pad]) -> list[Pad]:
        """Ensure exactly 64 pads."""
        if len(v) != 64:
            raise ValueError("Launchpad must have exactly 64 pads (8x8)")
        return v

    def get_pad(self, x: int, y: int) -> Pad:
        """Get pad at specific coordinates."""
        if not (0 <= x < 8 and 0 <= y < 8):
            raise ValueError(f"Invalid coordinates: ({x}, {y}). Must be 0-7.")
        return self.pads[y * 8 + x]

    def get_pad_by_note(self, note: int) -> Optional[Pad]:
        """Get pad by MIDI note number (0-63)."""
        if not 0 <= note < 64:
            return None
        y = note // 8
        x = note % 8
        return self.get_pad(x, y)

    def note_to_xy(self, note: int) -> tuple[int, int]:
        """Convert MIDI note to (x, y) coordinates."""
        y = note // 8
        x = note % 8
        return (x, y)

    def xy_to_note(self, x: int, y: int) -> int:
        """Convert (x, y) coordinates to MIDI note."""
        return y * 8 + x

    def clear_all(self) -> None:
        """Clear all pads."""
        for pad in self.pads:
            pad.clear()

    @property
    def assigned_pads(self) -> list[Pad]:
        """Get all pads that have samples assigned."""
        return [pad for pad in self.pads if pad.is_assigned]

    @classmethod
    def create_empty(cls, model: LaunchpadModel = LaunchpadModel.LAUNCHPAD_X) -> "Launchpad":
        """Create a new empty Launchpad."""
        return cls(model=model)
