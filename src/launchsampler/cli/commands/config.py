"""
Auto-generated config command using ModelCLIBuilder.

This command is auto-generated from the AppConfig Pydantic model using
ModelCLIBuilder. It provides a complete CLI interface for managing
application configuration with built-in validation and type safety.

Benefits of auto-generation:
    - Auto-updates when AppConfig fields change
    - Type-safe (Pydantic → Click type mapping)
    - Consistent error handling via ModelManagerService
    - Built-in validate/reset commands
    - Custom validators via ValidatorRegistry
    - Less boilerplate, DRY principle

Commands:
    - config show [--field FIELD]           # Display configuration
    - config set --option VALUE ...         # Update configuration
    - config validate                       # Validate config file
    - config reset [--field FIELD]          # Reset to defaults
"""

from pathlib import Path

from launchsampler.audio import AudioDevice
from launchsampler.model_manager.cli import ModelCLIBuilder, ValidatorRegistry
from launchsampler.models import AppConfig


# Register custom validators
@ValidatorRegistry.register("default_audio_device")
def validate_audio_device(device_id: int) -> tuple[bool, str | None]:
    """
    Validate audio device ID.

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        is_valid, hostapi_name, device_name = AudioDevice._is_valid_device(device_id)

        if not is_valid:
            _, api_names = AudioDevice._get_platform_apis()
            return (
                True,  # Still accept, but warn
                f"Warning: Device '{device_name}' uses {hostapi_name}. "
                f"Recommended: {api_names} for low-latency",
            )
        else:
            return True, f"Using device: {device_name} ({hostapi_name})"

    except ValueError:
        return (
            False,
            f"Device ID {device_id} not found. "
            "Use 'launchsampler audio list' to see available devices.",
        )


# Create CLI builder for AppConfig
builder = ModelCLIBuilder(
    model_type=AppConfig,
    config_path=Path.home() / ".launchsampler" / "config.json",
    field_overrides={
        "default_audio_device": {
            "short": "a",
            "help": 'Audio device ID or use "reset --field default_audio_device" for system default',
        },
        "default_buffer_size": {
            "short": "b",
            "help": "Audio buffer size in frames (larger = more stable, higher latency)",
        },
        "sets_dir": {"help": "Directory where sample sets are stored"},
        "midi_poll_interval": {"help": "MIDI polling interval in seconds"},
        "auto_save": {"help": "Automatically save sets after changes"},
    },
)

# Build the config command group
config = builder.build_group(name="config", help="Configure Launchpad Sampler settings")


# The config command structure:
# - config [--field FIELD]                      # Shows config values (default, human-readable)
# - config set --audio-device N --buffer-size N # Set field values and save
# - config validate [field1 field2 ...]         # Validate with [OK]/[FAIL] and type info
# - config reset [field1 field2 ...]            # Reset to defaults (prompts for confirmation)
