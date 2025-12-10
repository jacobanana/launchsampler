"""Sample model for audio file metadata."""

from pathlib import Path

from pydantic import BaseModel, Field, field_serializer, field_validator

from launchsampler.models.color import Color


class Sample(BaseModel):
    """Audio sample metadata (not the actual audio data)."""

    name: str = Field(description="Sample name")
    path: Path = Field(description="Path to audio file")
    color: Color | None = Field(
        default=None,
        description="Optional custom color (overrides playback mode color when set)",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Validate that path is a Path object."""
        if not isinstance(v, Path):
            return Path(v)
        return v

    @field_serializer("path")
    def serialize_path(self, path: Path) -> str:
        """Serialize Path to string using forward slashes for portability."""
        return path.as_posix()

    @classmethod
    def from_file(cls, path: Path) -> "Sample":
        """Create Sample from file path."""
        return cls(name=path.stem, path=path)

    def exists(self) -> bool:
        """Check if the audio file exists."""
        return self.path.exists()
