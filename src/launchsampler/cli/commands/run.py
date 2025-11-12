"""Run command implementation."""

import logging
import time
from pathlib import Path

import click

from launchsampler.audio import AudioDevice
from launchsampler.launchpad import LaunchpadController, LaunchpadManager
from launchsampler.models import Color, Launchpad, PlaybackMode, Sample

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

    logger.info("Starting MIDI-controlled Launchpad sampler")

    # Validate samples directory
    if not samples_dir.exists():
        click.echo(f"Error: Samples directory not found: {samples_dir}", err=True)
        click.echo("Create the directory and add some WAV files", err=True)
        raise click.Abort()

    # Find audio files
    extensions = ['*.wav', '*.mp3', '*.flac']
    sample_files = []
    for ext in extensions:
        sample_files.extend(samples_dir.glob(ext))
    if not sample_files:
        click.echo(f"Error: No audio files found in {samples_dir}", err=True)
        raise click.Abort()

    logger.info(f"Found {len(sample_files)} samples")

    # Create Launchpad configuration
    launchpad = Launchpad.create_empty()

    # Load and assign samples to pads
    for i, sample_file in enumerate(sample_files[:64]):  # Max 64 pads
        sample = Sample.from_file(sample_file)
        sample_name_lower = sample_file.stem.lower()

        # Set mode based on sample name (convention)
        if "tone" in sample_name_lower or "loop" in sample_name_lower:
            mode = PlaybackMode.LOOP
            color = Color(r=0, g=127, b=0)  # Green for LOOP
        elif "hold" in sample_name_lower:
            mode = PlaybackMode.HOLD
            color = Color(r=0, g=0, b=127)  # Blue for HOLD
        else:
            mode = PlaybackMode.ONE_SHOT
            color = Color(r=127, g=0, b=0)  # Red for ONE_SHOT

        # Assign to pad
        pad = launchpad.pads[i]
        pad.sample = sample
        pad.color = color
        pad.mode = mode
        pad.volume = 0.1

        logger.info(f"Pad {i}: {sample.name} ({mode.value})")

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

    with manager:
        # Load all samples
        for i in range(64):
            pad = launchpad.pads[i]
            if pad.sample:
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
                    logger.info(f"Pad {pad_index} pressed: {pad.sample.name} ({pad.mode.value})")
                    manager.trigger_pad(pad_index)

            def on_pad_released(pad_index: int):
                """Handle pad release - stop if LOOP or HOLD mode."""
                pad = launchpad.pads[pad_index]
                if pad.sample and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
                    logger.info(f"Pad {pad_index} released: stopping {pad.mode.value}")
                    manager.release_pad(pad_index)

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
