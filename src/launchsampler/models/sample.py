"""Sample models for audio file and Spotify track metadata."""

import re
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Discriminator, Field, Tag, field_serializer, field_validator


class AudioSample(BaseModel):
    """Audio sample metadata for file-based samples (not the actual audio data)."""

    type: Literal["audio"] = Field(default="audio", description="Sample type discriminator")
    name: str = Field(description="Sample name")
    path: Path = Field(description="Path to audio file")

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
    def from_file(cls, path: Path) -> "AudioSample":
        """Create AudioSample from file path."""
        return cls(name=path.stem, path=path)

    def exists(self) -> bool:
        """Check if the audio file exists."""
        return self.path.exists()


class SpotifySample(BaseModel):
    """Spotify track metadata for streaming samples."""

    type: Literal["spotify"] = Field(default="spotify", description="Sample type discriminator")
    name: str = Field(description="Track name (auto-populated from Spotify if not provided)")
    spotify_uri: str = Field(description="Spotify URI (e.g., spotify:track:4iV5W9uYEdYUVa79Axb7Rh)")

    @field_validator("spotify_uri")
    @classmethod
    def validate_spotify_uri(cls, v: str) -> str:
        """Validate and normalize Spotify URI format."""
        # If it's already a valid URI, return it
        if re.match(r"^spotify:track:[a-zA-Z0-9]{22}$", v):
            return v

        # Try to parse as Spotify share link
        parsed_uri = cls._parse_spotify_link(v)
        if parsed_uri:
            return parsed_uri

        raise ValueError(
            f"Invalid Spotify URI or link: {v}. "
            "Expected format: 'spotify:track:TRACK_ID' or Spotify share link"
        )

    @staticmethod
    def _parse_spotify_link(link: str) -> str | None:
        """
        Parse Spotify share link to extract track URI.

        Supports formats:
        - https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh
        - https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh?si=abc123
        - spotify:track:4iV5W9uYEdYUVa79Axb7Rh

        Returns:
            Spotify URI string or None if parsing fails
        """
        try:
            parsed = urlparse(link)

            # Handle open.spotify.com links
            if parsed.netloc == "open.spotify.com":
                # Path format: /track/TRACK_ID
                match = re.match(r"^/track/([a-zA-Z0-9]{22})$", parsed.path)
                if match:
                    return f"spotify:track:{match.group(1)}"

            return None
        except Exception:
            return None

    @classmethod
    def from_link(cls, link: str, name: str | None = None) -> "SpotifySample":
        """
        Create SpotifySample from Spotify share link.

        Args:
            link: Spotify share link (e.g., https://open.spotify.com/track/...)
            name: Optional name for the sample. If not provided, uses track ID.

        Returns:
            SpotifySample instance

        Raises:
            ValueError: If link is not a valid Spotify link
        """
        # The validator will handle link parsing
        sample = cls(name=name or "Spotify Track", spotify_uri=link)

        # Extract track ID for default name if name wasn't provided
        if name is None:
            track_id = sample.spotify_uri.split(":")[-1]
            sample = cls(name=f"Track {track_id[:8]}", spotify_uri=sample.spotify_uri)

        return sample

    @property
    def track_id(self) -> str:
        """Extract track ID from Spotify URI."""
        return self.spotify_uri.split(":")[-1]


def _get_sample_type(data: dict) -> str:
    """Discriminator function for Sample union type."""
    if isinstance(data, dict):
        return data.get("type", "audio")  # Default to audio for backward compatibility
    return "audio"


# Union type for both sample types using Pydantic's discriminator pattern
Sample = Annotated[
    Annotated[AudioSample, Tag("audio")] | Annotated[SpotifySample, Tag("spotify")],
    Discriminator(_get_sample_type),
]


# Backward compatibility: expose from_file as a module-level function
def sample_from_file(path: Path) -> AudioSample:
    """Create an AudioSample from file path (backward compatibility helper)."""
    return AudioSample.from_file(path)
