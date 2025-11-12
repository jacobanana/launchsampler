"""Run command implementation."""

import logging
import queue
import threading
import time
from pathlib import Path

import click

from launchsampler.audio import AudioDevice
from launchsampler.launchpad import LaunchpadController, LaunchpadManager
from launchsampler.models import Launchpad, PlaybackMode

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

    # Create Launchpad configuration from samples directory
    # This auto-configures modes/colors based on filename conventions
    try:
        launchpad = Launchpad.from_sample_directory(
            samples_dir=samples_dir,
            auto_configure=True,
            default_volume=0.1
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Create the directory and add some WAV files", err=True)
        raise click.Abort()

    num_samples = len(launchpad.assigned_pads)
    click.echo(f"Found {num_samples} sample(s)")

    # Create audio device
    try:
        audio_device_obj = AudioDevice(
            device=audio_device,
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            low_latency=True
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nUse 'launchsampler list audio' to see available devices", err=True)
        raise click.Abort()

    # Create manager with device
    manager = LaunchpadManager(audio_device_obj)

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

    with manager:
        # Load all assigned samples into the audio manager
        for i, pad in enumerate(launchpad.pads):
            if pad.is_assigned:
                success = manager.load_sample(i, pad)
                if not success:
                    logger.error(f"Failed to load sample for pad {i}")

        # Create MIDI controller
        with LaunchpadController(poll_interval=2.0) as midi_controller:
            logger.info("LaunchpadController started")

            # Wire up callbacks
            def on_pad_pressed(pad_index: int):
                """Handle pad press - trigger playback."""
                pad = launchpad.pads[pad_index]
                if pad.sample:
                    manager.trigger_pad(pad_index)
                    # Non-blocking output - enqueue message
                    output_queue.put_nowait(f"▶ Pad {pad_index}: {pad.sample.name} ({pad.mode.value})")

            def on_pad_released(pad_index: int):
                """Handle pad release - stop if LOOP or HOLD mode."""
                pad = launchpad.pads[pad_index]
                if pad.sample and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
                    manager.release_pad(pad_index)
                    # Non-blocking output - enqueue message
                    output_queue.put_nowait(f"■ Pad {pad_index} stopped")

            # Register callbacks
            midi_controller.on_pad_pressed(on_pad_pressed)
            midi_controller.on_pad_released(on_pad_released)

            click.echo("\nReady! Press pads on your Launchpad")
            click.echo("Press Ctrl+C to exit\n")
            click.echo("Playback modes:")
            click.echo("  Red (ONE_SHOT): Plays fully, ignores release")
            click.echo("  Green (LOOP): Loops until released")
            click.echo("  Blue (HOLD): Plays while held, stops on release")

            try:
                # Keep running
                while True:
                    time.sleep(1)

                    # Show active voices (debug)
                    active = manager.active_voices
                    if active > 0:
                        logger.debug(f"Active voices: {active}")

            except KeyboardInterrupt:
                click.echo("\nExiting...")
