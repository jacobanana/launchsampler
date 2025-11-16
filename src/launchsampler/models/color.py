"""Color model for LED control."""

from pydantic import BaseModel, Field, field_validator


class Color(BaseModel):
    """RGB color for Launchpad LED."""

    r: int = Field(ge=0, le=127, description="Red (0-127)")
    g: int = Field(ge=0, le=127, description="Green (0-127)")
    b: int = Field(ge=0, le=127, description="Blue (0-127)")

    @field_validator("r", "g", "b")
    @classmethod
    def validate_rgb(cls, v: int) -> int:
        """Ensure RGB values are in valid range."""
        if not 0 <= v <= 127:
            raise ValueError("RGB values must be between 0 and 127")
        return v

    @classmethod
    def off(cls) -> "Color":
        """Create off (black) color."""
        return cls(r=0, g=0, b=0)

    def to_rgb_tuple(self) -> tuple[int, int, int]:
        """Convert to RGB tuple."""
        return (self.r, self.g, self.b)

    def to_hex(self) -> str:
        """Convert to CSS hex color string (e.g., '#FF00FF').

        Note: Launchpad uses 0-127 range, but CSS hex uses 0-255 range.
        This method scales the values by 2 for proper CSS display.

        Returns:
            str: Hex color string in format '#RRGGBB'
        """
        # Scale from 0-127 to 0-255 for CSS compatibility
        r_scaled = self.r * 2
        g_scaled = self.g * 2
        b_scaled = self.b * 2
        return f"#{r_scaled:02X}{g_scaled:02X}{b_scaled:02X}"
