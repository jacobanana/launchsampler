from pathlib import Path
from typing import Optional

import click

from launchsampler.audio import AudioDevice
from launchsampler.models import AppConfig


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

    # Load configuration (from file or defaults)
    config = AppConfig.load_or_default()

    # Update config with CLI arguments (only if explicitly provided)
    if audio_device is not None:
        if audio_device.lower() == "default":
            config.default_audio_device = None
            click.echo("Audio device reset to system default")
        else:
            try:
                device_id = int(audio_device)

                # Validate device exists
                try:
                    is_valid, hostapi_name, device_name = AudioDevice._is_valid_device(device_id)
                    config.default_audio_device = device_id

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
                    config.default_audio_device = device_id

            except ValueError:
                click.echo(f"Error: Invalid audio device value '{audio_device}'. Must be a number or 'default'.", err=True)
                return

    if buffer_size is not None:
        config.default_buffer_size = buffer_size

    # Save config so preferences are remembered for next time
    config.save()

    click.echo("\nCurrent configuration:")
    click.echo(f"  Audio Device ID: {config.default_audio_device or 'default (system)'}")
    click.echo(f"  Buffer Size: {config.default_buffer_size}")
    click.echo(f"  Sets Directory: {config.sets_dir}")
    click.echo(f"  MIDI Poll Interval: {config.midi_poll_interval}")
    click.echo("")
    click.echo("Configuration updated successfully." if (audio_device or buffer_size) else "No changes made.")