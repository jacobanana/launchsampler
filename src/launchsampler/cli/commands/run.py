"""Run command implementation."""

import logging
import time
from pathlib import Path

import click

from launchsampler.core import SamplerApplication
from launchsampler.models import AppConfig

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )


@click.command()
@click.option(
    '--audio-device',
    '-a',
    type=int,
    default=None,
    help='Audio device ID (use "launchsampler list audio" to see available devices)'
)
@click.option(
    '--sample-rate',
    '-r',
    type=int,
    default=48000,
    help='Sample rate in Hz (default: 48000)'
)
@click.option(
    '--buffer-size',
    '-b',
    type=int,
    default=64,
    help='Audio buffer size in frames (default: 64, lower = less latency)'
)
@click.option(
    '--samples-dir',
    '-s',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("test_samples"),
    help='Directory containing WAV samples (default: test_samples/)'
)
def run(audio_device: int, sample_rate: int, buffer_size: int, samples_dir: Path):
    """
    Run MIDI-controlled Launchpad sampler.

    This starts the sampler with MIDI hot-plug support and low-latency audio playback.
    Samples are loaded from the specified directory and mapped to Launchpad pads.

    Examples:

      # Run with default settings
      launchsampler run

      # Use specific audio device
      launchsampler run --audio-device 13

      # Use larger buffer for stability (higher latency)
      launchsampler run --buffer-size 128

      # Use custom samples directory
      launchsampler run --samples-dir ./my_samples
    """
    setup_logging()

    click.echo("Starting MIDI-controlled Launchpad sampler...")

    # Create application with configuration
    config = AppConfig(
        sample_rate=sample_rate,
        buffer_size=buffer_size,
        samples_dir=samples_dir
    )

    # Event callback for UI output
    def on_pad_event(event_type: str, pad_index: int):
        """Handle pad events and display to user."""
        if not app.launchpad:
            return

        pad = app.launchpad.pads[pad_index]
        if event_type == "pressed" and pad.sample:
            click.echo(f"▶ Pad {pad_index}: {pad.sample.name} ({pad.mode.value})")
        elif event_type == "released":
            click.echo(f"■ Pad {pad_index} stopped")

    app = SamplerApplication(config=config, on_pad_event=on_pad_event)

    # Load samples
    try:
        launchpad = app.load_samples_from_directory(samples_dir)
        click.echo(f"Found {len(launchpad.assigned_pads)} sample(s)")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Create the directory and add some WAV files", err=True)
        raise click.Abort()

    # Start audio and MIDI
    try:
        app.start(
            audio_device=audio_device,
            sample_rate=sample_rate,
            buffer_size=buffer_size
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nUse 'launchsampler list audio' to see available devices", err=True)
        raise click.Abort()

    click.echo("\nReady! Press pads on your Launchpad")
    click.echo("Press Ctrl+C to exit\n")
    click.echo("Playback modes:")
    click.echo("  Red (ONE_SHOT): Plays fully, ignores release")
    click.echo("  Green (LOOP): Loops until released")
    click.echo("  Blue (HOLD): Plays while held, stops on release")

    # Event loop
    try:
        while True:
            time.sleep(1)

            # Show active voices (debug)
            active = app.active_voices
            if active > 0:
                logger.debug(f"Active voices: {active}")

    except KeyboardInterrupt:
        click.echo("\nExiting...")
    finally:
        app.stop()
