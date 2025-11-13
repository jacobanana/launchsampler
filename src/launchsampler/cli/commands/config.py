from pathlib import Path
from typing import Optional

import click

from launchsampler.models import AppConfig


@click.command()
@click.option(
    '--audio-device',
    '-a',
    type=int,
    default=None,
    help='Audio device ID (use "launchsampler list audio" to see available devices)'
)
@click.option(
    '--buffer-size',
    '-b',
    type=int,
    default=None,
    help='Audio buffer size in frames (default: 512)'
)
def config(audio_device: Optional[int], buffer_size: Optional[int]):
    """
    Configure default settings for Launchpad sampler.

    This command sets default audio device and buffer size.

    Examples:

      # Print current configuration
      launchsampler config

      # Set specific audio device
      launchsampler config --audio-device 13

      # Set larger buffer for stability (higher latency)
      launchsampler config --buffer-size 128
    """

    click.echo("Configuring default settings for Launchpad sampler...")

    # Load configuration (from file or defaults)
    config = AppConfig.load_or_default()

    # Update config with CLI arguments (only if explicitly provided)
    if audio_device is not None:
        config.default_audio_device = audio_device

    if buffer_size is not None:
        config.default_buffer_size = buffer_size

    # Save config so preferences are remembered for next time
    config.save()

    click.echo("Current configuration:")
    click.echo(f"  Audio Device ID: {config.default_audio_device}")
    click.echo(f"  Buffer Size: {config.default_buffer_size}")
    click.echo(f"  Sets Directory: {config.sets_dir}")
    click.echo(f"  MIDI Poll Interval: {config.midi_poll_interval}")
    click.echo("")
    click.echo("Configuration updated successfully." if (audio_device or buffer_size) else "No changes made.")