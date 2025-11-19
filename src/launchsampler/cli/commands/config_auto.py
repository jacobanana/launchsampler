"""
Auto-generated config command using ModelCLIBuilder.

This is an example of how to use ModelCLIBuilder to create a CLI command
from a Pydantic model. It replaces the manual config command with an
auto-generated one that stays in sync with the AppConfig model.

Usage:
    Replace the manual config command in cli/main.py with this one:

    ```python
    from .commands.config_auto import config
    ```

Benefits over manual command:
    - Auto-updates when AppConfig changes
    - Type-safe (Pydantic → Click type mapping)
    - Consistent error handling
    - Built-in validate/reset commands
    - Less boilerplate code
"""

from pathlib import Path

from launchsampler.audio import AudioDevice
from launchsampler.cli.model_cli_builder import ModelCLIBuilder, ValidatorRegistry
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
                f"Recommended: {api_names} for low-latency"
            )
        else:
            return True, f"Using device: {device_name} ({hostapi_name})"

    except ValueError:
        return (
            False,
            f"Device ID {device_id} not found. "
            "Use 'launchsampler audio list' to see available devices."
        )


# Create CLI builder for AppConfig
builder = ModelCLIBuilder(
    model_type=AppConfig,
    config_path=Path.home() / ".launchsampler" / "config.json",
    field_overrides={
        "default_audio_device": {
            "short": "a",
            "help": 'Audio device ID or use "reset --field default_audio_device" for system default'
        },
        "default_buffer_size": {
            "short": "b",
            "help": "Audio buffer size in frames (larger = more stable, higher latency)"
        },
        "sets_dir": {
            "help": "Directory where sample sets are stored"
        },
        "midi_poll_interval": {
            "help": "MIDI polling interval in seconds"
        },
        "auto_save": {
            "help": "Automatically save sets after changes"
        }
    }
)

# Build the config command group
config = builder.build_group(
    name="config",
    help="Configure Launchpad Sampler settings"
)


# The config command now has:
# - config show [--field FIELD]
# - config set --audio-device N --buffer-size N ...
# - config validate
# - config reset [--field FIELD]
