"""Run command implementation."""

import logging
import time
import queue
import threading
from pathlib import Path
from typing import Optional

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
    '--buffer-size',
    '-b',
    type=int,
    default=None,
    help='Audio buffer size in frames (default: from config, typically 512)'
)
@click.option(
    '--samples-dir',
    '-s',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("test_samples"),
    help='Directory containing WAV samples (default: test_samples/)'
)
def run(audio_device: Optional[int], buffer_size: Optional[int], samples_dir: Path):
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

    # Load configuration (from file or defaults)
    config = AppConfig.load_or_default()

    # Update config with CLI arguments (only if explicitly provided)
    config.samples_dir = samples_dir

    if audio_device is not None:
        config.default_audio_device = audio_device

    if buffer_size is not None:
        config.default_buffer_size = buffer_size

    # Save config so preferences are remembered for next time
    config.save()

    # Create non-blocking output queue for console messages
    output_queue = queue.Queue()

    def output_worker():
        """Background thread for console output (non-blocking I/O)."""
        while True:
            msg = output_queue.get()
            if msg is None:  # Shutdown signal
                break
            click.echo(msg)

    # Start output worker thread
    output_thread = threading.Thread(target=output_worker, daemon=True)
    output_thread.start()

    # Event callback for UI output
    def on_pad_event(event_type: str, pad_index: int):
        """Handle pad events and display to user."""
        if not app.launchpad:
            return

        pad = app.launchpad.pads[pad_index]
        if event_type == "pressed" and pad.sample:
            # Non-blocking output - enqueue message
            output_queue.put_nowait(f"▶ Pad {pad_index}: {pad.sample.name} ({pad.mode.value})")
        elif event_type == "released":
            output_queue.put_nowait(f"■ Pad {pad_index} stopped")

    app = SamplerApplication(config=config, on_pad_event=on_pad_event)

    # Load samples (uses config.samples_dir)
    try:
        launchpad = app.load_samples_from_directory()
        click.echo(f"Found {len(launchpad.assigned_pads)} sample(s)")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Create the directory and add some WAV files", err=True)
        raise click.Abort()

    # Start audio and MIDI (config defaults are used for None values)
    try:
        app.start(
            audio_device=audio_device,
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
