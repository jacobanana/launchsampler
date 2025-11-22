"""Color model for LED control."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Color(BaseModel):
    """Standard 8-bit RGB color model.

    Uses standard 8-bit RGB (0-255) as the application's color representation.
    Device-specific conversions (e.g., 7-bit for MIDI SysEx) are handled
    by device adapters.

    The model is frozen to ensure hashability, which is required for
    LRU caching in color approximation functions.
    """

    model_config = ConfigDict(frozen=True)

    r: int = Field(ge=0, le=255, description="Red (0-255)")
    g: int = Field(ge=0, le=255, description="Green (0-255)")
    b: int = Field(ge=0, le=255, description="Blue (0-255)")

    @field_validator("r", "g", "b")
    @classmethod
    def validate_rgb(cls, v: int) -> int:
        """Ensure RGB values are in valid range."""
        if not 0 <= v <= 255:
            raise ValueError("RGB values must be between 0 and 255")
        return v

    @classmethod
    def off(cls) -> "Color":
        """Create off (black) color."""
        return cls(r=0, g=0, b=0)

    def to_rgb_tuple(self) -> tuple[int, int, int]:
        """Convert to RGB tuple."""
        return (self.r, self.g, self.b)

    def to_7bit(self) -> tuple[int, int, int]:
        """Convert to 7-bit RGB for MIDI SysEx messages.

        Hardware devices like Launchpad use 7-bit values (0-127) for MIDI.
        This method downsamples 8-bit (0-255) to 7-bit using right bit shift.

        Returns:
            tuple[int, int, int]: RGB values in 0-127 range

        Example:
            >>> color = Color(r=255, g=128, b=0)
            >>> color.to_7bit()
            (127, 64, 0)
        """
        return (self.r >> 1, self.g >> 1, self.b >> 1)

    def to_hex(self) -> str:
        """Convert to CSS hex color string (e.g., '#FF0000').

        Returns:
            str: Hex color string in format '#RRGGBB'

        Example:
            >>> color = Color(r=255, g=0, b=0)
            >>> color.to_hex()
            '#FF0000'
        """
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"
