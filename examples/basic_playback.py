"""Basic example: Load and play samples sequentially."""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from launchsampler.audio import AudioManager
from launchsampler.models import Pad, Sample, PlaybackMode, Color


def main():
    """Load samples and play them back one after the other."""

    # Find test samples directory
    samples_dir = Path("test_samples")

    if not samples_dir.exists():
        print(f"Error: {samples_dir} directory not found!")
        print("Run test_audio_manager.py first to generate test samples.")
        return

    # Find all WAV files
    sample_files = sorted(samples_dir.glob("*.wav"))

    if not sample_files:
        print(f"No WAV files found in {samples_dir}")
        return

    print(f"Found {len(sample_files)} samples:")
    for i, file in enumerate(sample_files):
        print(f"  {i}: {file.name}")

    # Create audio manager
    print("\nStarting audio engine...")
    with AudioManager(sample_rate=44100, buffer_size=512) as manager:
        print("Audio engine started\n")

        # Load samples into pads
        print("Loading samples...")
        for i, sample_file in enumerate(sample_files):
            pad = Pad(x=i, y=0)
            pad.sample = Sample.from_file(sample_file)
            pad.mode = PlaybackMode.ONE_SHOT
            pad.volume = 0.7

            manager.load_sample(i, pad)
            print(f"  Loaded pad {i}: {sample_file.name}")

        print(f"\nPlaying {len(sample_files)} samples sequentially...\n")

        # Play each sample
        for i, sample_file in enumerate(sample_files):
            print(f"Playing: {sample_file.name}")
            manager.trigger_pad(i)

            # Wait for sample to finish
            time.sleep(0.6)

        print("\nPlayback complete!")


if __name__ == "__main__":
    main()
