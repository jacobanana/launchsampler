from pathlib import Path
from typing import Optional

import click

from launchsampler.audio import AudioDevice
from launchsampler.models import AppConfig
from launchsampler.services import ModelManagerService
from launchsampler.exceptions import ConfigurationError


@click.command()
@click.option(
    '--audio-device',
    '-a',
    type=str,
    default=None,
    help='Audio device ID or "default" to use system default (use "launchsampler audio list" to see available devices)'
)
@click.option(
    '--buffer-size',
    '-b',
    type=int,
    default=None,
    help='Audio buffer size in frames (default: 512)'
)
def config(audio_device: Optional[str], buffer_size: Optional[int]):
    """
    Configure default settings for Launchpad sampler.

    This command sets default audio device and buffer size.

    Examples:

      # Print current configuration
      launchsampler config

      # Set specific audio device
      launchsampler config --audio-device 13

      # Reset to system default audio device
      launchsampler config --audio-device default

      # Set larger buffer for stability (higher latency)
      launchsampler config --buffer-size 128
    """

    click.echo("Configuring default settings for Launchpad sampler...")

    # Load configuration and create service
    config_path = Path.home() / ".launchsampler" / "config.json"

    try:
        config = AppConfig.load_or_default(config_path)
    except ConfigurationError as e:
        click.echo(f"Error loading configuration: {e.user_message}", err=True)
        if e.recovery_hint:
            click.echo(f"Suggestion: {e.recovery_hint}", err=True)
        return

    # Create ModelManagerService for managing updates
    config_service = ModelManagerService[AppConfig](
        AppConfig,
        config,
        default_path=config_path
    )

    # Update config with CLI arguments (only if explicitly provided)
    if audio_device is not None:
        if audio_device.lower() == "default":
            config_service.set("default_audio_device", None)
            click.echo("Audio device reset to system default")
        else:
            try:
                device_id = int(audio_device)

                # Validate device exists
                try:
                    is_valid, hostapi_name, device_name = AudioDevice._is_valid_device(device_id)
                    config_service.set("default_audio_device", device_id)

                    if not is_valid:
                        _, api_names = AudioDevice._get_platform_apis()
                        click.echo(
                            f"Warning: Device '{device_name}' (ID: {device_id}) uses Host API '{hostapi_name}'. "
                            f"Only {api_names} devices are recommended for low-latency playback.",
                            err=True
                        )
                    else:
                        click.echo(f"Audio device set to: {device_name} ({hostapi_name})")

                except ValueError as e:
                    click.echo(
                        f"Warning: Device ID {device_id} not found or invalid. "
                        f"The configuration has been saved, but playback may fail. "
                        f"Use 'launchsampler audio list --all' to see available devices.",
                        err=True
                    )
                    config_service.set("default_audio_device", device_id)

            except ValueError:
                click.echo(f"Error: Invalid audio device value '{audio_device}'. Must be a number or 'default'.", err=True)
                return

    if buffer_size is not None:
        try:
            config_service.set("default_buffer_size", buffer_size)
        except ConfigurationError as e:
            click.echo(f"Error: {e.user_message}", err=True)
            return

    # Save config so preferences are remembered for next time
    try:
        config_service.save()
    except ConfigurationError as e:
        click.echo(f"Error saving configuration: {e.user_message}", err=True)
        if e.recovery_hint:
            click.echo(f"Suggestion: {e.recovery_hint}", err=True)
        return

    # Display current configuration
    current_config = config_service.get_all()
    click.echo("\nCurrent configuration:")
    click.echo(f"  Audio Device ID: {current_config.get('default_audio_device') or 'default (system)'}")
    click.echo(f"  Buffer Size: {current_config.get('default_buffer_size')}")
    click.echo(f"  Sets Directory: {current_config.get('sets_dir')}")
    click.echo(f"  MIDI Poll Interval: {current_config.get('midi_poll_interval')}")
    click.echo(f"  Auto-save: {current_config.get('auto_save')}")
    click.echo("")
    click.echo("Configuration updated successfully." if (audio_device or buffer_size) else "No changes made.")