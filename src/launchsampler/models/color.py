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
    def red(cls) -> "Color":
        """Create red color."""
        return cls(r=127, g=0, b=0)

    @classmethod
    def green(cls) -> "Color":
        """Create green color."""
        return cls(r=0, g=127, b=0)

    @classmethod
    def blue(cls) -> "Color":
        """Create blue color."""
        return cls(r=0, g=0, b=127)

    @classmethod
    def yellow(cls) -> "Color":
        """Create yellow color."""
        return cls(r=127, g=127, b=0)

    @classmethod
    def off(cls) -> "Color":
        """Create off (black) color."""
        return cls(r=0, g=0, b=0)

    def to_rgb_tuple(self) -> tuple[int, int, int]:
        """Convert to RGB tuple."""
        return (self.r, self.g, self.b)
