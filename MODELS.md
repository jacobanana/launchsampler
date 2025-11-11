# Data Models

This document describes the Pydantic data models for the Launchpad Sampler application.

## Overview

All models are lean, type-safe Pydantic models that handle:
- Validation
- Serialization/Deserialization (JSON)
- Type hints for IDE support
- Configuration management

**Note:** These models store **metadata only**. Actual audio data is handled separately using dataclasses/NumPy arrays for performance.

## Models

### Enums ([enums.py](src/launchsampler/models/enums.py))

#### `PlaybackMode`
Audio playback modes:
- `ONE_SHOT` - Play once, stop
- `LOOP` - Loop continuously
- `HOLD` - Play while held, stop on release

#### `LaunchpadModel`
Supported hardware models:
- `LAUNCHPAD_X`
- `LAUNCHPAD_MINI`
- `LAUNCHPAD_PRO`

### Color ([color.py](src/launchsampler/models/color.py))

RGB color model for LED control (0-127 range for MIDI compatibility).

```python
from launchsampler.models import Color

# Predefined colors
red = Color.red()
green = Color.green()
blue = Color.blue()
yellow = Color.yellow()
off = Color.off()

# Custom color
custom = Color(r=64, g=100, b=127)

# Get as tuple
rgb = red.to_rgb_tuple()  # (127, 0, 0)
```

### Sample ([sample.py](src/launchsampler/models/sample.py))

Audio sample **metadata** (not the actual audio data).

```python
from pathlib import Path
from launchsampler.models import Sample

# Create from file
sample = Sample.from_file(Path("kick.wav"))

# Properties
print(sample.name)       # "kick"
print(sample.path)       # Path("kick.wav")
print(sample.exists())   # True/False
```

### Pad ([pad.py](src/launchsampler/models/pad.py))

Represents a single pad in the 8x8 grid.

```python
from launchsampler.models import Pad, Sample, Color, PlaybackMode

# Create empty pad
pad = Pad.empty(x=0, y=0)

# Assign sample
pad.sample = Sample.from_file(Path("kick.wav"))
pad.color = Color.red()
pad.mode = PlaybackMode.ONE_SHOT
pad.volume = 0.8

# Check state
print(pad.is_assigned)   # True
print(pad.position)      # (0, 0)

# Clear pad
pad.clear()
```

### Launchpad ([launchpad.py](src/launchsampler/models/launchpad.py))

The complete 8x8 grid (64 pads).

```python
from launchsampler.models import Launchpad, LaunchpadModel

# Create empty grid
launchpad = Launchpad.create_empty(LaunchpadModel.LAUNCHPAD_X)

# Access pads
pad = launchpad.get_pad(x=0, y=0)
pad_by_note = launchpad.get_pad_by_note(0)  # MIDI note 0-63

# Coordinate conversion
x, y = launchpad.note_to_xy(15)  # (7, 1)
note = launchpad.xy_to_note(0, 0)  # 0

# Get assigned pads
assigned = launchpad.assigned_pads

# Clear all
launchpad.clear_all()
```

### Set ([set.py](src/launchsampler/models/set.py))

A saved configuration of pad assignments.

```python
from pathlib import Path
from launchsampler.models import Set

# Create new set
my_set = Set.create_empty("drums_kit_1")

# Modify launchpad
my_set.launchpad.get_pad(0, 0).sample = Sample.from_file(Path("kick.wav"))

# Save to file
my_set.save_to_file(Path("sets/drums.json"))

# Load from file
loaded_set = Set.load_from_file(Path("sets/drums.json"))

# Update timestamp
my_set.update_timestamp()
```

### AppConfig ([config.py](src/launchsampler/models/config.py))

Application configuration and settings.

```python
from launchsampler.models import AppConfig

# Load or create default
config = AppConfig.load_or_default()

# Properties
print(config.sets_dir)           # Path to sets directory
print(config.samples_dir)        # Path to samples directory
print(config.sample_rate)        # 44100
print(config.buffer_size)        # 512
print(config.launchpad_model)    # LaunchpadModel.LAUNCHPAD_X
print(config.auto_save)          # True

# Save config
config.save()  # Saves to ~/.launchsampler/config.json
```

## File Structure

```
src/launchsampler/models/
├── __init__.py      # Exports all models
├── enums.py         # PlaybackMode, LaunchpadModel
├── color.py         # Color model
├── sample.py        # Sample metadata
├── pad.py           # Single pad
├── launchpad.py     # 8x8 grid
├── set.py           # Saved configuration
└── config.py        # App settings
```

## Design Principles

1. **Lean & Simple** - Only essential fields, no bloat
2. **Type-Safe** - Full Pydantic validation
3. **Serializable** - Easy JSON save/load
4. **Separation of Concerns** - Models are metadata only; audio data handled separately
5. **Easy to Use** - Intuitive factory methods and properties

## JSON Serialization

All models can be serialized to/from JSON:

```python
# Serialize
json_str = my_set.model_dump_json(indent=2)

# Deserialize
loaded = Set.model_validate_json(json_str)
```

## Next Steps

These models provide the foundation for:
- Audio engine (handles actual audio data)
- MIDI controller (sends/receives MIDI messages)
- Storage layer (save/load sets)
- UI layer (terminal or GUI display)
