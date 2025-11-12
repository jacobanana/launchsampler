# Audio Data Structures

This document describes the dataclass-based audio data structures for handling raw audio data and playback state.

## Overview

These are **dataclasses**, NOT Pydantic models, for performance reasons:
- Handle real-time audio processing with minimal overhead
- Store non-serializable data (NumPy arrays)
- Used internally by the audio engine
- Not part of the public API/serialization layer

## Architecture Pattern

This follows the **Separation of Concerns** pattern from context.md:

```
┌─────────────────────────────────────────────────────────────┐
│                    Pydantic Models Layer                    │
│  (Serializable metadata - saved to JSON files)             │
│  - Sample: file path, name, metadata                       │
│  - Pad: position, color, mode, volume                      │
│  - Set: configuration, timestamps                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Dataclass Data Layer                       │
│  (Non-serializable runtime data - in memory only)          │
│  - AudioData: NumPy arrays, actual audio buffers           │
│  - PlaybackState: position, playing flag, loop count       │
└─────────────────────────────────────────────────────────────┘
```

## Dataclasses

### AudioData ([data.py](src/launchsampler/audio/data.py))

Stores actual audio buffer data.

```python
from launchsampler.audio import AudioData
import numpy as np

# Create from NumPy array
sample_rate = 44100
audio_array = np.zeros(44100, dtype=np.float32)  # 1 second of silence
audio = AudioData.from_array(audio_array, sample_rate)

# Properties
print(audio.sample_rate)   # 44100
print(audio.num_channels)  # 1
print(audio.num_frames)    # 44100
print(audio.duration)      # 1.0 seconds
print(audio.shape)         # (44100,)

# Get mono version (converts stereo to mono)
mono_data = audio.get_mono()

# Normalize audio to target level
audio.normalize(target_level=0.95)
```

**Fields:**
- `data: NDArray[float32]` - Raw audio samples
- `sample_rate: int` - Sample rate in Hz
- `num_channels: int` - Number of channels (1=mono, 2=stereo)
- `num_frames: int` - Number of frames (samples per channel)

**Why dataclass?**
- NumPy arrays cannot be serialized by Pydantic
- Minimal overhead for audio processing
- Fast, simple, efficient

### PlaybackState ([data.py](src/launchsampler/audio/data.py))

Runtime playback state for a single pad.

```python
from launchsampler.audio import PlaybackState, AudioData
from launchsampler.models import PlaybackMode

# Create playback state
state = PlaybackState(
    mode=PlaybackMode.ONE_SHOT,
    volume=0.8,
    audio_data=audio  # Link to AudioData
)

# Start playback
state.start()

# Advance playback (called from audio callback)
state.advance(512)  # Advance by 512 frames

# Get audio frames for mixing
frames = state.get_frames(512)

# Check progress
print(state.progress)        # 0.0 to 1.0
print(state.time_elapsed)    # Seconds elapsed
print(state.time_remaining)  # Seconds remaining

# Stop playback
state.stop()

# Reset to beginning
state.reset()
```

**Fields:**
- `is_playing: bool` - Currently playing
- `position: float` - Current playback position (frames)
- `mode: PlaybackMode` - Playback mode (one_shot, loop, hold)
- `volume: float` - Playback volume (0.0-1.0)
- `audio_data: Optional[AudioData]` - Reference to audio buffer

**Methods:**
- `start()` - Start playback from beginning
- `stop()` - Stop playback
- `reset()` - Reset to initial state
- `advance(num_frames)` - Advance playback position (handles looping)
- `get_frames(num_frames)` - Get next audio frames with volume applied

**Why dataclass?**
- Changes rapidly during playback (minimal overhead needed)
- Not serializable (runtime state only)
- Simple, fast access in audio callback

## Usage Pattern

### 1. Load Audio File

```python
# Load WAV file (this would be in audio engine)
import soundfile as sf
from pathlib import Path

# Read audio file
data, sample_rate = sf.read("kick.wav", dtype='float32')

# Create AudioData
audio = AudioData.from_array(data, sample_rate)
```

### 2. Link to Pad Metadata

```python
from launchsampler.models import Pad, Sample, PlaybackMode, Color

# Create pad with metadata (Pydantic - serializable)
pad = Pad(x=0, y=0)
pad.sample = Sample.from_file(Path("kick.wav"))
pad.color = Color.red()
pad.mode = PlaybackMode.ONE_SHOT
pad.volume = 0.8

# Create playback state (dataclass - runtime only)
playback = PlaybackState(
    mode=pad.mode,
    volume=pad.volume,
    audio_data=audio  # Loaded separately
)
```

### 3. Audio Callback

```python
def audio_callback(output_buffer, num_frames):
    """Called by audio system to fill output buffer."""

    # Clear output
    output_buffer.fill(0.0)

    # Mix all playing pads
    for playback_state in active_playbacks:
        if playback_state.is_playing:
            # Get frames from this pad
            frames = playback_state.get_frames(num_frames)

            if frames is not None:
                # Mix into output
                output_buffer[:len(frames)] += frames

                # Advance position
                playback_state.advance(len(frames))
```

## Why This Design?

From context.md:

> **Separation of Concerns Pattern**
> - Pydantic models: Metadata, serialization, validation
> - Dataclasses: Raw data storage, performance-critical operations
> - Each class has one job

### Pydantic Models (Metadata)
✅ Serialize to JSON
✅ Validate on load
✅ Schema generation
✅ Configuration files
❌ NOT for audio buffers

### Dataclasses (Runtime Data)
✅ Minimal overhead (~100ns instantiation)
✅ Fast field access
✅ NumPy integration
✅ Real-time safe
❌ NOT serializable

## Performance Comparison

```python
# Pydantic validation overhead: ~10-50µs per instance
# Dataclass instantiation: ~100ns per instance

# In audio callback running at 512 frames, 44100 Hz:
# - Callback every ~11ms
# - Need to process 64 pads
# - Pydantic: 64 × 50µs = 3.2ms (too slow!)
# - Dataclass: 64 × 100ns = 6.4µs (perfect!)
```

## File Structure

```
src/launchsampler/audio/
├── __init__.py    # Exports: AudioData, PlaybackState
└── data.py        # Dataclass definitions
```

## Testing

Run `test_audio_data.py` to verify:

```bash
python test_audio_data.py
```

Tests cover:
- AudioData creation (mono/stereo)
- Normalization
- PlaybackState start/stop/advance
- Looping behavior
- Integration with Pydantic models

## Next Steps

With these dataclasses, you can now build:

1. **Audio loader** - Load WAV files into AudioData
2. **Audio mixer** - Mix multiple PlaybackState into output buffer
3. **Audio engine** - Manage audio callback and playback states
4. **Sample manager** - Map Pads to AudioData/PlaybackState

All using this clean separation between metadata (Pydantic) and runtime data (dataclasses).
