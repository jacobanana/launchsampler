"""Main entry point for launchsampler."""

import time
from pathlib import Path

from launchsampler.audio import AudioManager
from launchsampler.models import Pad, Sample, PlaybackMode


def main():
    """Load and play test samples."""

    # Find test samples directory
    samples_dir = Path("test_samples")

    if not samples_dir.exists():
        print("Creating test samples...")
        from examples.basic_playback import create_test_samples
        # You'll need to run test_audio_manager.py first
        print("Please run: python -m pytest tests/test_audio_manager.py")
        print("This will create test samples in test_samples/")
        return

    # Find all WAV files
    sample_files = sorted(samples_dir.glob("*.wav"))

    if not sample_files:
        print(f"No WAV files found in {samples_dir}")
        return

    print(f"Launchsampler - Found {len(sample_files)} samples\n")

    # Create audio manager
    with AudioManager(sample_rate=44100, buffer_size=512) as manager:
        # Load samples
        for i, sample_file in enumerate(sample_files):
            pad = Pad(x=i, y=0)
            pad.sample = Sample.from_file(sample_file)
            pad.mode = PlaybackMode.ONE_SHOT
            pad.volume = 0.7

            manager.load_sample(i, pad)
            print(f"[{i}] {sample_file.stem}")

        print(f"\nPlaying {len(sample_files)} samples...\n")

        # Play each sample
        for i in range(len(sample_files)):
            manager.trigger_pad(i)
            time.sleep(0.6)

        print("Done!")


if __name__ == "__main__":
    main()
