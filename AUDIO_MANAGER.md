# Audio Manager

Complete audio playback system using sounddevice for the Launchpad Sampler.

## Overview

The audio manager handles:
- Loading audio files (WAV, FLAC, OGG, etc.)
- Managing playback for 64 pads
- Real-time mixing in audio callback
- Thread-safe operations
- Low-latency playback

## Components

### 1. SampleLoader ([loader.py](src/launchsampler/audio/loader.py))

Loads audio files into AudioData structures.

```python
from launchsampler.audio import SampleLoader
from pathlib import Path

# Create loader
loader = SampleLoader(target_sample_rate=44100)

# Load audio file
audio = loader.load(Path("kick.wav"))

# Get file info without loading
info = SampleLoader.get_info(Path("kick.wav"))
print(f"Duration: {info['duration']}s, Rate: {info['sample_rate']} Hz")
```

**Features:**
- Supports WAV, FLAC, OGG, and other soundfile formats
- Optional resampling to target sample rate
- Automatic mono/stereo handling
- File validation

### 2. AudioMixer ([mixer.py](src/launchsampler/audio/mixer.py))

Mixes multiple audio sources into a single output.

```python
from launchsampler.audio import AudioMixer

# Create mixer
mixer = AudioMixer(num_channels=2)  # Stereo output

# Mix playback states
output = mixer.mix(playback_states, num_frames=512)

# Apply master volume
mixer.apply_master_volume(output, volume=0.8)

# Prevent clipping
mixer.soft_clip(output)  # Smooth tanh clipping
# or
mixer.clip(output)  # Hard [-1, 1] clipping
```

**Features:**
- Thread-safe mixing
- Automatic channel conversion (mono ↔ stereo)
- Soft clipping to prevent distortion
- Volume control

### 3. AudioManager ([manager.py](src/launchsampler/audio/manager.py))

Main audio engine managing everything.

```python
from launchsampler.audio import AudioManager
from launchsampler.models import Pad, Sample
from pathlib import Path

# Create and start audio manager
manager = AudioManager(
    sample_rate=44100,
    buffer_size=512,
    num_channels=2
)
manager.start()

# Create pad
pad = Pad(x=0, y=0)
pad.sample = Sample.from_file(Path("kick.wav"))
pad.mode = PlaybackMode.ONE_SHOT
pad.volume = 0.8

# Load sample
manager.load_sample(0, pad)

# Trigger playback
manager.trigger_pad(0)

# Stop when done
manager.stop()

# Or use context manager
with AudioManager() as manager:
    manager.load_sample(0, pad)
    manager.trigger_pad(0)
    time.sleep(1)
```

## AudioManager API

### Initialization

```python
AudioManager(
    sample_rate: int = 44100,      # Sample rate in Hz
    buffer_size: int = 512,        # Buffer size (lower = less latency)
    num_channels: int = 2,         # 1=mono, 2=stereo
    device: Optional[int] = None   # Output device ID (None = default)
)
```

### Stream Control

```python
manager.start()              # Start audio stream
manager.stop()               # Stop audio stream
manager.is_running           # Check if running (property)
```

### Sample Management

```python
# Load sample for a pad
manager.load_sample(pad_index: int, pad: Pad) -> bool

# Unload sample from pad
manager.unload_sample(pad_index: int)

# Clear audio cache to free memory
manager.clear_cache()
```

### Playback Control

```python
# Trigger pad (start playback)
manager.trigger_pad(pad_index: int)

# Release pad (for HOLD mode)
manager.release_pad(pad_index: int)

# Stop specific pad
manager.stop_pad(pad_index: int)

# Stop all pads
manager.stop_all()
```

### Runtime Updates

```python
# Update pad volume
manager.update_pad_volume(pad_index: int, volume: float)

# Update pad playback mode
manager.update_pad_mode(pad_index: int, mode: PlaybackMode)

# Set master volume
manager.set_master_volume(volume: float)
```

### Monitoring

```python
# Get playback info for a pad
info = manager.get_playback_info(pad_index: int)
# Returns: {'is_playing', 'progress', 'time_elapsed',
#           'time_remaining', 'mode', 'volume'}

# Get number of active voices
active = manager.active_voices
```

### Device Management

```python
# List available audio devices
devices = AudioManager.list_devices()

# Get default device
default = AudioManager.get_default_device()
```

## Usage Examples

### Basic Playback

```python
from launchsampler.audio import AudioManager
from launchsampler.models import Pad, Sample, PlaybackMode
from pathlib import Path
import time

with AudioManager() as manager:
    # Set up pad
    pad = Pad(x=0, y=0)
    pad.sample = Sample.from_file(Path("samples/kick.wav"))
    pad.mode = PlaybackMode.ONE_SHOT
    pad.volume = 0.8

    # Load and play
    manager.load_sample(0, pad)
    manager.trigger_pad(0)

    time.sleep(1)  # Let it play
```

### Looping Sample

```python
with AudioManager() as manager:
    # Set up looping pad
    pad = Pad(x=0, y=0)
    pad.sample = Sample.from_file(Path("samples/loop.wav"))
    pad.mode = PlaybackMode.LOOP
    pad.volume = 0.5

    manager.load_sample(0, pad)
    manager.trigger_pad(0)  # Start loop

    time.sleep(3)

    manager.stop_pad(0)  # Stop loop
```

### Multiple Pads

```python
with AudioManager() as manager:
    # Load multiple pads
    samples = {
        0: "kick.wav",
        1: "snare.wav",
        2: "hihat.wav",
    }

    for idx, filename in samples.items():
        pad = Pad(x=idx, y=0)
        pad.sample = Sample.from_file(Path(f"samples/{filename}"))
        pad.mode = PlaybackMode.ONE_SHOT
        pad.volume = 0.7
        manager.load_sample(idx, pad)

    # Play a simple pattern
    pattern = [0, 1, 0, 2, 0, 1, 0, 2]
    for pad_idx in pattern:
        manager.trigger_pad(pad_idx)
        time.sleep(0.25)
```

### HOLD Mode (Play While Held)

```python
with AudioManager() as manager:
    pad = Pad(x=0, y=0)
    pad.sample = Sample.from_file(Path("samples/tone.wav"))
    pad.mode = PlaybackMode.HOLD

    manager.load_sample(0, pad)

    # Simulate button press
    manager.trigger_pad(0)
    time.sleep(0.5)

    # Simulate button release
    manager.release_pad(0)
```

### Monitor Playback

```python
with AudioManager() as manager:
    pad = Pad(x=0, y=0)
    pad.sample = Sample.from_file(Path("samples/long.wav"))
    manager.load_sample(0, pad)
    manager.trigger_pad(0)

    # Monitor progress
    while True:
        info = manager.get_playback_info(0)
        if not info['is_playing']:
            break

        print(f"Progress: {info['progress']:.1%}, "
              f"Elapsed: {info['time_elapsed']:.2f}s")
        time.sleep(0.1)
```

## Performance

### Latency

Latency = `buffer_size / sample_rate`

```python
# Low latency (11.6ms)
AudioManager(buffer_size=512, sample_rate=44100)

# Very low latency (5.8ms) - may cause dropouts on slower systems
AudioManager(buffer_size=256, sample_rate=44100)

# Higher latency but more stable (23ms)
AudioManager(buffer_size=1024, sample_rate=44100)
```

### Memory

Audio cache stores loaded samples in memory:
- 1 second mono @ 44.1kHz = ~176 KB
- 1 second stereo @ 44.1kHz = ~352 KB
- 64 pads × 1 second = ~11-22 MB

Use `manager.clear_cache()` to free memory if needed.

### CPU

The audio callback runs in a real-time thread:
- Must complete in < `buffer_size / sample_rate` seconds
- Locked sections are minimal (< 1µs)
- Mixing is optimized NumPy operations

## Thread Safety

All public methods are thread-safe:
- `load_sample()`, `trigger_pad()`, etc. can be called from any thread
- Internal lock protects shared state
- Audio callback has its own thread

## Architecture

```
┌─────────────────────────────────────────────┐
│           AudioManager (Public API)          │
│  ┌─────────┬─────────┬────────────────────┐ │
│  │ Loader  │  Mixer  │  Playback States   │ │
│  └─────────┴─────────┴────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  Audio Callback │ ◄── sounddevice
         │  (Real-time)    │
         └─────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  Audio Hardware │
         └─────────────────┘
```

## Testing

Run comprehensive tests:

```bash
python test_audio_manager.py
```

Tests include:
- ✓ SampleLoader (loading, resampling, info)
- ✓ AudioMixer (mixing, clipping, channel conversion)
- ✓ AudioManager (loading, playback, control)
- ✓ Live playback test (optional, requires user input)

## File Structure

```
src/launchsampler/audio/
├── __init__.py       # Exports all components
├── data.py           # AudioData, PlaybackState (dataclasses)
├── loader.py         # SampleLoader
├── mixer.py          # AudioMixer
└── manager.py        # AudioManager (main class)
```

## Next Steps

With the audio manager complete, you can now:

1. **Integrate with MIDI** - Connect Launchpad hardware
2. **Build UI** - Terminal or GUI interface
3. **Add storage** - Save/load full configurations
4. **Create patterns** - Sequence playback

The audio engine is production-ready!
