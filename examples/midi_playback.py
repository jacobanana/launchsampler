"""Example: MIDI-controlled playback with Launchpad.

This example demonstrates:
- Hot-plug MIDI device detection
- Event callbacks wiring MIDI to AudioManager
- Proper playback mode handling:
  - ONE_SHOT: Plays entire sample, ignores note-off
  - LOOP: Loops until note-off
  - HOLD: Stops immediately on note-off
"""

import logging
import time
from pathlib import Path

from launchsampler.audio import AudioManager
from launchsampler.midi import LaunchpadController
from launchsampler.models import Color, Launchpad, Pad, PlaybackMode, Sample

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    # TODO: help user select audio device interactively
    device = 13
    """Run MIDI-controlled playback example."""
    logger.info("Starting MIDI-controlled Launchpad sampler")

    # Print all available audio devices to help you choose
    # Look for ASIO devices for lowest latency
    AudioManager.print_devices()

    # To use a specific device (like ASIO), set device=X where X is the device ID from print_devices()
    # For example: AudioManager(buffer_size=64, device=5, low_latency=False)
    # Note: ASIO devices don't need low_latency=True (they have their own low-latency API)

    # Create a Launchpad configuration
    launchpad = Launchpad.create_empty()

    # Load some samples (adjust paths as needed)
    samples_dir = Path("test_samples")
    if not samples_dir.exists():
        logger.error(f"Samples directory not found: {samples_dir}")
        logger.info("Create test_samples directory and add some WAV files")
        return

    # Assign samples to pads with different playback modes
    sample_files = list(samples_dir.glob("*.wav"))
    if not sample_files:
        logger.error("No WAV files found in test_samples/")
        return

    logger.info(f"Found {len(sample_files)} samples")

    # Assign samples to pads with specific modes
    # tone.wav -> LOOP mode (pad 0)
    # kick.wav -> ONE_SHOT mode (pad 1)
    # Others -> Alternate between modes
    for i, sample_file in enumerate(sample_files[:8]):
        if i >= 64:  # Only 64 pads
            break

        sample = Sample.from_file(sample_file)
        sample_name_lower = sample_file.stem.lower()

        # Set mode based on sample name
        if "tone" in sample_name_lower:
            mode = PlaybackMode.LOOP
            color = Color(r=0, g=127, b=0)  # Green for LOOP
            logger.info(f"Found tone sample - setting to LOOP mode")
        else:
            mode = PlaybackMode.ONE_SHOT
            color = Color(r=127, g=0, b=0)  # Red for ONE_SHOT
            logger.info(f"Found {sample.name} sample - setting to ONE_SHOT mode")

        # Get the existing pad and modify it
        pad = launchpad.pads[i]
        pad.sample = sample
        pad.color = color
        pad.mode = mode
        pad.volume = 0.1

        logger.info(f"Pad {i}: {sample.name} ({mode.value})")

    # Create AudioManager with ultra-low-latency settings
    # buffer_size=64: ~1.5ms latency (recommended for live performance)
    # buffer_size=128: ~3ms latency (good balance)
    # buffer_size=256: ~6ms latency (safer for stability)
    # device=None: Uses system default (change to specific device ID for ASIO)
    with AudioManager(device=device, sample_rate=48000, buffer_size=64, low_latency=True) as audio_manager:

        # Load all samples into AudioManager
        for i in range(64):
            pad = launchpad.pads[i]
            if pad.sample:
                success = audio_manager.load_sample(i, pad)
                if success:
                    logger.info(f"Loaded sample for pad {i}")
                else:
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
                    audio_manager.trigger_pad(pad_index)
                else:
                    logger.debug(f"Pad {pad_index} pressed but no sample assigned")

            def on_pad_released(pad_index: int):
                """Handle pad release - stop if LOOP or HOLD mode."""
                pad = launchpad.pads[pad_index]
                if pad.sample:
                    # ONE_SHOT: Ignore release, let sample play fully
                    # LOOP: Stop looping
                    # HOLD: Stop immediately
                    if pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
                        logger.info(f"Pad {pad_index} released: stopping {pad.mode.value}")
                        audio_manager.release_pad(pad_index)

            # Register callbacks
            midi_controller.on_pad_pressed(on_pad_pressed)
            midi_controller.on_pad_released(on_pad_released)

            logger.info("Ready! Press pads on your Launchpad")
            logger.info("Press Ctrl+C to exit")
            logger.info("")
            logger.info("Playback modes:")
            logger.info("  Red (ONE_SHOT): Plays fully, ignores release")
            logger.info("  Green (LOOP): Loops until released")
            logger.info("  Blue (HOLD): Plays while held, stops on release")

            try:
                # Keep running
                while True:
                    time.sleep(1)

                    # Show active voices
                    active = audio_manager.active_voices
                    if active > 0:
                        logger.debug(f"Active voices: {active}")

            except KeyboardInterrupt:
                logger.info("\nExiting...")


if __name__ == "__main__":
    main()
