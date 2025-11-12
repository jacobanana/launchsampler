# Examples

Example scripts demonstrating how to use the Launchpad Sampler.

## Prerequisites

Generate test samples first:

```bash
# Run tests to generate sample files
pytest tests/test_audio_manager.py
```

This creates `test_samples/` directory with:
- `kick.wav` - Low frequency kick drum
- `snare.wav` - Noise-based snare
- `hihat.wav` - High frequency hi-hat
- `tone.wav` - 440 Hz tone

## Examples

### basic_playback.py

Load and play samples sequentially.

```bash
python examples/basic_playback.py
```

**What it does:**
1. Finds all WAV files in `test_samples/`
2. Loads them into AudioManager
3. Plays each sample one after another
4. Waits 0.6s between samples

**Key concepts:**
- Creating an `AudioManager`
- Loading samples into pads
- Triggering playback
- Using context manager for cleanup

## Using in Your Own Code

```python
from launchsampler.audio import AudioManager
from launchsampler.models import Pad, Sample, PlaybackMode
from pathlib import Path

# Create manager
with AudioManager(sample_rate=44100, buffer_size=512) as manager:
    # Create and load pad
    pad = Pad(x=0, y=0)
    pad.sample = Sample.from_file(Path("your_sample.wav"))
    pad.mode = PlaybackMode.ONE_SHOT
    pad.volume = 0.8

    manager.load_sample(0, pad)

    # Play
    manager.trigger_pad(0)

    # Wait for it to finish
    import time
    time.sleep(1)
```

## More Examples Coming Soon

- Pattern playback (drum patterns)
- Live triggering (keyboard input)
- Save/load sets
- Volume control
- MIDI integration
