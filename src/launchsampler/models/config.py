"""Application configuration model."""

from pathlib import Path

from pydantic import BaseModel, Field, field_serializer

from launchsampler.model_manager.persistence import PydanticPersistence


class AppConfig(BaseModel):
    """Application configuration and settings."""

    # Paths
    sets_dir: Path = Field(
        default_factory=lambda: Path.home() / ".launchsampler" / "sets",
        description="Directory for saved sets",
    )

    # Audio defaults (used if not overridden at runtime)
    default_audio_device: int | None = Field(
        default=None,
        description=(
            "Default audio output device ID (None = system default). "
            "If the device is invalid or unavailable, automatically falls back to "
            "the OS default device or the first available low-latency device."
        ),
    )
    default_buffer_size: int = Field(default=512, description="Default audio buffer size in frames")

    # MIDI settings
    midi_poll_interval: float = Field(
        default=2.0, description="How often to check for MIDI device changes (seconds)"
    )

    # Panic button settings
    panic_button_cc_control: int = Field(
        default=19, description="MIDI CC control number for panic button (stop all audio)"
    )
    panic_button_cc_value: int = Field(
        default=127, description="MIDI CC value for panic button trigger"
    )

    # Session settings
    last_set: str | None = Field(default=None, description="Last loaded set name")
    auto_save: bool = Field(default=True, description="Auto-save on changes")

    @field_serializer("sets_dir")
    def serialize_path(self, path: Path) -> str:
        """Serialize Path to string."""
        return str(path)

    def ensure_directories(self) -> None:
        """Create config directories if they don't exist."""
        self.sets_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_or_default(cls, path: Path | None = None) -> "AppConfig":
        """
        Load config from file or return default.

        This is a convenience method that handles the default path logic
        and ensures directories are created.

        Args:
            path: Path to config file. If None, uses default location
                  (~/.launchsampler/config.json).

        Raises:
            ConfigFileInvalidError: If config file has invalid JSON syntax
            ConfigValidationError: If config values fail validation
        """
        if path is None:
            path = Path.home() / ".launchsampler" / "config.json"

        # Load using PydanticPersistence
        config = PydanticPersistence.load_or_default(path, cls)

        # Domain-specific post-processing
        config.ensure_directories()
        return config

    def save(self, path: Path | None = None) -> None:
        """Save config to file."""
        if path is None:
            path = Path.home() / ".launchsampler" / "config.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))
