# Launchpad Sampler - Architecture Overview

Complete overview of the data layer architecture.

## Design Pattern: Separation of Concerns

Following the pattern from context.md, we separate **metadata** (serializable) from **runtime data** (performance-critical).

```
┌───────────────────────────────────────────────────────────────┐
│                     METADATA LAYER                            │
│                  (Pydantic Models)                            │
│  • Serializable to JSON                                       │
│  • Configuration files                                        │
│  • Type-safe validation                                       │
├───────────────────────────────────────────────────────────────┤
│  Sample    - Audio file path, name, metadata                 │
│  Pad       - Position (x,y), color, mode, volume             │
│  Launchpad - 8x8 grid of pads                                │
│  Set       - Saved configuration with timestamps              │
│  AppConfig - Application settings                            │
└───────────────────────────────────────────────────────────────┘
                            │
                            │ Links via file path
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                    RUNTIME DATA LAYER                         │
│                    (Dataclasses)                              │
│  • NOT serializable                                           │
│  • Performance-critical                                       │
│  • Real-time audio processing                                │
├───────────────────────────────────────────────────────────────┤
│  AudioData      - NumPy arrays, actual audio buffers          │
│  PlaybackState  - Position, playing flag, loop count          │
└───────────────────────────────────────────────────────────────┘
```

## Complete Data Model

### Metadata Layer (Pydantic)

#### Core Enums
```python
PlaybackMode (str, Enum)
├── ONE_SHOT  # Play once
├── LOOP      # Loop continuously
└── HOLD      # Play while held

LaunchpadModel (str, Enum)
├── LAUNCHPAD_X
├── LAUNCHPAD_MINI
└── LAUNCHPAD_PRO
```

#### Models
```python
Color (BaseModel)
├── r: int (0-127)
├── g: int (0-127)
└── b: int (0-127)
    ├── off()
    └── to_rgb_tuple()

Sample (BaseModel)
├── name: str
├── path: Path
├── duration: Optional[float]
└── sample_rate: Optional[int]
    ├── from_file(path)
    └── exists()

Pad (BaseModel)
├── x: int (0-7)
├── y: int (0-7)
├── sample: Optional[Sample]
├── color: Color
├── mode: PlaybackMode
└── volume: float (0.0-1.0)
    ├── is_assigned (property)
    ├── position (property)
    ├── clear()
    └── empty(x, y)

Launchpad (BaseModel)
├── model: LaunchpadModel
└── pads: list[Pad] (64 total)
    ├── get_pad(x, y)
    ├── get_pad_by_note(note)
    ├── note_to_xy(note)
    ├── xy_to_note(x, y)
    ├── clear_all()
    ├── assigned_pads (property)
    └── create_empty(model)

Set (BaseModel)
├── name: str
├── launchpad: Launchpad
├── created_at: datetime
├── modified_at: datetime
└── description: Optional[str]
    ├── save_to_file(path)
    ├── load_from_file(path)
    ├── create_empty(name)
    └── update_timestamp()

AppConfig (BaseModel)
├── sets_dir: Path
├── samples_dir: Path
├── sample_rate: int
├── buffer_size: int
├── launchpad_model: LaunchpadModel
├── midi_input_device: Optional[str]
├── midi_output_device: Optional[str]
├── last_set: Optional[str]
└── auto_save: bool
    ├── ensure_directories()
    ├── load_or_default(path)
    └── save(path)
```

### Runtime Data Layer (Dataclasses)

```python
@dataclass
AudioData
├── data: NDArray[float32]       # Raw audio samples
├── sample_rate: int
├── num_channels: int
└── num_frames: int
    ├── from_array(data, sample_rate)
    ├── duration (property)
    ├── shape (property)
    ├── get_mono()
    └── normalize(target_level)

@dataclass
PlaybackState
├── is_playing: bool
├── position: float
├── mode: PlaybackMode
├── volume: float
└── audio_data: Optional[AudioData]
    ├── start()
    ├── stop()
    ├── reset()
    ├── advance(num_frames)
    ├── get_frames(num_frames)
    ├── progress (property)
    ├── time_elapsed (property)
    └── time_remaining (property)
```

## File Structure

```
src/launchsampler/
├── models/                    # Pydantic models (metadata)
│   ├── __init__.py
│   ├── enums.py              # PlaybackMode, LaunchpadModel
│   ├── color.py              # Color
│   ├── sample.py             # Sample
│   ├── pad.py                # Pad
│   ├── launchpad.py          # Launchpad
│   ├── set.py                # Set
│   └── config.py             # AppConfig
│
└── audio/                     # Dataclasses (runtime data)
    ├── __init__.py
    └── data.py               # AudioData, PlaybackState
```

## Usage Flow

### 1. Configuration (Metadata)

```python
# Create/load configuration
config = AppConfig.load_or_default()

# Create new set
my_set = Set.create_empty("drums")

# Configure a pad
pad = my_set.launchpad.get_pad(0, 0)
pad.sample = Sample.from_file(Path("kick.wav"))
pad.color = Color.red()
pad.mode = PlaybackMode.ONE_SHOT
pad.volume = 0.8

# Save to file
my_set.save_to_file(config.sets_dir / "drums.json")
```

### 2. Audio Loading (Runtime)

```python
# Load audio file
import soundfile as sf

data, sr = sf.read(pad.sample.path, dtype='float32')
audio = AudioData.from_array(data, sr)

# Create playback state
playback = PlaybackState(
    mode=pad.mode,
    volume=pad.volume,
    audio_data=audio
)
```

### 3. Playback (Runtime)

```python
# Trigger playback
playback.start()

# In audio callback
def callback(output, num_frames):
    frames = playback.get_frames(num_frames)
    if frames is not None:
        output[:len(frames)] += frames
        playback.advance(len(frames))
```

## Why This Architecture?

### Pydantic Benefits
✅ **Type safety** - Validation on assignment
✅ **Serialization** - Save/load from JSON
✅ **Documentation** - Self-documenting schemas
✅ **IDE support** - Full autocomplete
✅ **User-facing** - API and configuration layer

### Dataclass Benefits
✅ **Performance** - Minimal overhead (~100ns)
✅ **Simplicity** - No validation overhead
✅ **NumPy integration** - Direct array access
✅ **Real-time safe** - No GC pressure
✅ **Internal-only** - Audio engine layer

### Performance Numbers

```
Pydantic model creation:   ~10-50µs
Dataclass creation:         ~100ns
Speed difference:           100-500x faster

In audio callback (every ~11ms at 512 frames):
- Need to process 64 pads
- Dataclass: 64 × 100ns = 6.4µs ✅
- Pydantic: 64 × 50µs = 3.2ms ❌ (30% of available time!)
```

## Testing

```bash
# Test Pydantic models
python test_models.py

# Test dataclasses
python test_audio_data.py
```

## Documentation

- **[MODELS.md](MODELS.md)** - Pydantic models API
- **[AUDIO_DATA.md](AUDIO_DATA.md)** - Dataclass structures
- **[MODEL_SUMMARY.md](MODEL_SUMMARY.md)** - Quick reference

## Next Components

With complete data layer, you can build:

1. **Audio Engine** - Load files, mix, playback
2. **MIDI Controller** - Launchpad communication
3. **Storage Manager** - Save/load sets
4. **UI Layer** - Terminal interface

All using this solid, tested foundation!
