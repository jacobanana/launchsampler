# Devices Folder Architecture - Feynman Diagram

## 🎯 The Big Picture (Explain Like I'm 5)

Think of the devices system like a **LEGO factory**:

- **devices.json** = The instruction manual (says "use these LEGO pieces for a Launchpad Pro")
- **Registry** = The factory worker who reads the manual and builds the toy
- **Adapters** = The actual LEGO pieces (buttons, lights, electronics) - translate generic commands to device-specific messages
- **Device Controller** = The kid playing with the finished toy

---

## 📦 What Each File Does (One Sentence Each)

| File | What It Does |
|------|--------------|
| **protocols.py** | Defines the "rules" - what any device MUST be able to do (parse buttons, control LEDs) |
| **config.py** | Holds settings for each device (what it's called, which USB ports to use) |
| **registry.py** | The "factory" - looks at USB devices and builds the right controller |
| **device.py** | Wraps everything together into one neat package |
| **input.py** | Translates MIDI messages (like "note 36 pressed") into logical events ("pad 5 pressed") |
| **devices.json** | Database of all supported devices with their quirks |
| **adapters/launchpad_mk3.py** | The brains for MK3 Launchpads (note mapping + LED control) |
| **adapters/launchpad_sysex.py** | Low-level translator - speaks Launchpad's secret language (SysEx) |
| **launchpad/controller.py** | High-level "remote control" that users actually interact with |

---

## 🔌 Connection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER APPLICATION                            │
│                    (Your Sampler Software)                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    Uses high-level API
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DeviceController                              │
│                  (launchpad/controller.py)                          │
│                                                                     │
│  🎮 What it does:                                                   │
│    - Manages connection to the device                              │
│    - Provides user-friendly methods (set_pad_color, etc.)          │
│    - Handles observers (notify when buttons pressed)               │
│    - Hides all the complexity below                                │
└──────────┬─────────────────┬────────────────────────┬───────────────┘
           │                 │                        │
    Asks for help    Detects devices         Sends messages
           ↓                 ↓                        ↓
   ┌───────────────┐ ┌──────────────┐      ┌─────────────────┐
   │ DeviceRegistry│ │ MidiManager  │      │  MidiManager    │
   │ (registry.py) │ │ (generic)    │      │  (output)       │
   └───────┬───────┘ └──────────────┘      └─────────────────┘
           │
    Loads config &
    creates device
           ↓
┌──────────────────────────────────────────────────────────────────────┐
│                        DeviceRegistry                                │
│                       (registry.py)                                  │
│                                                                      │
│  🏭 What it does:                                                    │
│    1. Loads devices.json at startup                                 │
│    2. When USB device appears, checks if name matches patterns      │
│    3. Selects the right USB ports (OS-specific rules)               │
│    4. Assembles a GenericDevice from parts:                         │
│       - Mapper (note translation)                                   │
│       - Input handler (MIDI parser)                                 │
│       - Output handler (LED controller)                             │
└───────┬──────────────────────────────────────────────────────────────┘
        │
        │ Reads configuration
        ↓
┌────────────────────────────────────────────────────────────────────┐
│                        devices.json                                │
│                     (Configuration File)                           │
│                                                                    │
│  📋 Contains:                                                      │
│    - Family: "launchpad_mk3"                                       │
│    - Detection patterns: ["Launchpad Pro", "LPProMK3"]            │
│    - Capabilities: {num_pads: 64, grid_size: 8}                   │
│    - Port selection rules (Windows/Mac/Linux)                     │
│    - SysEx header: [0, 32, 41, 2, 14]                             │
│    - Implements: "LaunchpadMK3" ← Links to code                   │
└───────┬────────────────────────────────────────────────────────────┘
        │
        │ Points to implementation
        ↓
┌────────────────────────────────────────────────────────────────────┐
│              adapters/__init__.py                           │
│              (Implementation Registry)                             │
│                                                                    │
│  🔍 Registry lookup:                                               │
│    "LaunchpadMK3" → (LaunchpadMK3Mapper, LaunchpadMK3Output)      │
│                                                                    │
│  To add new device:                                                │
│    register_implementation("APC40", APC40Mapper, APC40Output)     │
└───────┬────────────────────────────────────────────────────────────┘
        │
        │ Returns mapper & output classes
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       GenericDevice                                 │
│                        (device.py)                                  │
│                                                                     │
│  📦 Simple wrapper that holds:                                      │
│    - config: DeviceConfig                                           │
│    - input: GenericInput (MIDI → Events)                            │
│    - output: LaunchpadMK3Output (Events → LEDs)                     │
│                                                                     │
│  Two sides of the coin:                                             │
│    ┌─────────────────────────────────────────────────────┐          │
│    │              INPUT SIDE                             │          │
│    └─────────────────────────────────────────────────────┘          │
└─────┬───────────────────────────────────────────────────┬───────────┘
      │                                                   │
      ↓                                                   ↓
```

### INPUT SIDE (Button Press → Your Code)

```
Hardware Button Press
      ↓
[MIDI Message: note_on 36, velocity 100]
      ↓
┌──────────────────────────────────────┐
│      GenericInput                    │
│       (input.py)                     │
│                                      │
│  parse_message(msg):                 │
│    if msg.type == 'note_on':         │
│      index = mapper.note_to_index(36)│
│      return PadPressEvent(index=5)   │
└────────────┬─────────────────────────┘
             │ Uses mapper
             ↓
┌──────────────────────────────────────┐
│   LaunchpadMK3Mapper                 │
│   (adapters/launchpad_mk3.py) │
│                                      │
│  note_to_index(36):                  │
│    offset = 11                       │
│    row_spacing = 10                  │
│    note_index = note - offset = 25   │
│    row = 25 // 10 = 2                │
│    col = 25 % 10 = 5                 │
│    return row * 8 + col = 21         │
│                                      │
│  Hardware layout:                    │
│    Note 11 = bottom-left (0,0)       │
│    Note 36 = pad at (2,5)            │
│    Logical index 21                  │
└──────────────────────────────────────┘
      ↓
[PadPressEvent(pad_index=21, velocity=100)]
      ↓
Your application observers get notified
```

### OUTPUT SIDE (Your Code → LED Lights Up)

```
Your code calls:
set_pad_color(index=21, Color(255, 0, 0))
      ↓
┌──────────────────────────────────────┐
│   LaunchpadMK3Output                 │
│   (adapters/launchpad_mk3.py) │
│                                      │
│  set_led(index=21, color):           │
│    note = mapper.index_to_note(21)   │
│    # Returns note 36                 │
│    sysex = LaunchpadSysEx.led_lighting([│
│      (RGB, 36, 255, 0, 0)            │
│    ])                                │
│    midi_manager.send(sysex)          │
└────────────┬─────────────────────────┘
             │ Uses mapper
             ↓
┌──────────────────────────────────────┐
│   LaunchpadMK3Mapper                 │
│   (adapters/launchpad_mk3.py) │
│                                      │
│  index_to_note(21):                  │
│    offset = 11                       │
│    row_spacing = 10                  │
│    row = 21 // 8 = 2                 │
│    col = 21 % 8 = 5                  │
│    note = offset + (row*10) + col    │
│    return 11 + 20 + 5 = 36           │
└──────────────────────────────────────┘
      ↓
┌──────────────────────────────────────┐
│   LaunchpadSysEx                     │
│   (adapters/launchpad_sysex.py)│
│                                      │
│  led_lighting(specs):                │
│    Creates SysEx message:            │
│    [0xF0] Header Command Data [0xF7] │
│                                      │
│    [0xF0, 0, 32, 41, 2, 14, 0x03,    │
│     3, 36, 255, 0, 0, 0xF7]          │
│                                      │
│    3 = RGB mode                      │
│    36 = MIDI note                    │
│    255, 0, 0 = Red color             │
└──────────────────────────────────────┘
      ↓
[MIDI SysEx Message]
      ↓
Hardware LED turns RED
```

---

## 🔑 Key Design Insights

### 1. **Logical vs Hardware Indices**

```
User thinks:    "Light up pad at position (row=2, col=5)"
                         ↓
Application:    "Light up logical index 21"  (row*8 + col)
                         ↓
Mapper:         "That's MIDI note 36"        (hardware-specific)
                         ↓
SysEx:          [0xF0, ..., 36, 255, 0, 0]   (protocol message)
                         ↓
Hardware:       Pad lights up RED
```

**Why this matters**: You can swap Launchpad models without changing your app code!

### 2. **The Registry is a "Smart Factory"**

```
USB Device Connected: "Launchpad Pro MK3 MIDI"
                              ↓
Registry checks devices.json: "Does 'LPProMK3' match patterns?"
                              ↓ YES
Registry: "This is a Launchpad Pro MK3"
         "It implements: LaunchpadMK3"
         "Prefer port: LPProMK3 MIDI 0"
                              ↓
Registry looks up implementation: get_implementation("LaunchpadMK3")
                              ↓ Returns
         (LaunchpadMK3Mapper, LaunchpadMK3Output)
                              ↓
Registry creates: GenericDevice(
    mapper=LaunchpadMK3Mapper(),
    input=GenericInput(mapper),
    output=LaunchpadMK3Output(midi_manager, config)
)
                              ↓
Returns fully assembled device to DeviceController
```

### 3. **Port Selection (The Tricky Part)**

Many Launchpads show up as **multiple MIDI ports** on Windows/Mac/Linux:

```
Windows sees:
  - "LPProMK3 MIDI 0"  ← Use this one for input (has button events)
  - "LPProMK3 MIDI 1"  ← Use this one for output (accepts SysEx)
  - "LPProMK3 DAW"     ← Ignore (for DAW mode)

Mac sees:
  - "Launchpad Pro MK3 LPProMK3 MIDI"
  - "Launchpad Pro MK3 DAW Out"  ← Exclude this

Linux sees different names!
```

**config.py** handles this with OS-specific rules:

```python
{
  "input_port_selection": {
    "windows": {
      "prefer": ["LPProMK3 MIDI 0"],  # Try this first
      "fallback": "MIDI 1"            # If not found, use this
    },
    "darwin": {  # macOS
      "exclude": ["DAW"]               # Never use ports with "DAW"
    }
  }
}
```

---

## 🎨 Why Launchpad Folder ≠ Implementations Folder

This is the key architectural distinction:

### `adapters/` = **Device-Specific Logic**

```
Purpose:     "How do I talk to THIS specific hardware?"
Audience:    Internal (used by registry)
Contains:    - Note mapping (MIDI note ↔ logical index)
             - SysEx message builders
             - LED control protocols
Extends:     One folder per device family
Example:     launchpad_mk3.py, launchpad_sysex.py
```

**You add new files here when supporting a new device model**

### `launchpad/` = **User-Facing API**

```
Purpose:     "Give me a simple remote control for ANY Launchpad"
Audience:    External applications
Contains:    - Connection management
             - Observer notifications
             - Lifecycle (start/stop)
             - Generic API (works with all devices)
Extends:     NEVER (it composes the registry)
Example:     controller.py
```

**You use this from your application code, never edit it for new devices**

### The Relationship

```
┌─────────────────────────────────────────────────────────┐
│           DeviceController                           │
│           (User presses buttons here)                   │
│                                                         │
│  Methods:                                               │
│    - set_pad_color(index, color)                        │
│    - start() / stop()                                   │
│    - register_observer(callback)                        │
│                                                         │
│  Doesn't know ANYTHING about:                           │
│    - MIDI notes                                         │
│    - SysEx messages                                     │
│    - Hardware differences                               │
└────────────┬────────────────────────────────────────────┘
             │
             │ Uses
             ↓
┌─────────────────────────────────────────────────────────┐
│                DeviceRegistry                           │
│                (The middleman)                          │
└────────────┬────────────────────────────────────────────┘
             │
             │ Loads & assembles
             ↓
┌─────────────────────────────────────────────────────────┐
│           adapters/                              │
│           (Hardware-specific details)                   │
│                                                         │
│  LaunchpadMK3Mapper:                                    │
│    - note 11 = bottom-left                              │
│    - row_spacing = 10                                   │
│                                                         │
│  LaunchpadMK3Output:                                    │
│    - Initialize: Enter programmer mode                  │
│    - set_led: Build RGB SysEx                           │
│                                                         │
│  LaunchpadSysEx:                                        │
│    - Header: [0, 32, 41, 2, 14]                         │
│    - Command 0x03: LED lighting                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🧩 Adding a New Device (Step by Step)

Let's say you want to support the "APC40 MK2":

### Step 1: Create Implementation

Create `adapters/apc40_mk2.py`:

```python
from typing import Optional
from ..input import NoteMapper
from ..protocols import DeviceOutput

class APC40Mapper(NoteMapper):
    """APC40 has 5x8 grid starting at note 53."""

    def note_to_index(self, note: int) -> Optional[int]:
        # APC40-specific layout
        offset = 53
        if note < offset or note >= offset + 40:
            return None
        note_index = note - offset
        row = note_index // 8
        col = note_index % 8
        return row * 8 + col

    def index_to_note(self, index: int) -> int:
        return 53 + index

class APC40Output(DeviceOutput):
    def initialize(self) -> None:
        # Send APC40 initialization sequence
        pass

    def set_led(self, index: int, color: Color) -> None:
        note = APC40Mapper().index_to_note(index)
        # APC40-specific LED message
        msg = mido.Message('note_on', note=note, velocity=color_to_velocity(color))
        self._midi.send(msg)

    # ... other methods
```

### Step 2: Register Implementation

In `adapters/__init__.py`:

```python
from .apc40_mk2 import APC40Mapper, APC40Output

register_implementation("APC40", APC40Mapper, APC40Output)
```

### Step 3: Add Configuration

In `devices.json`:

```json
{
  "family": "apc40",
  "manufacturer": "Akai",
  "implements": "APC40",
  "detection_patterns": ["APC40"],
  "capabilities": {
    "num_pads": 40,
    "grid_size": 8,
    "supports_rgb": false
  },
  "input_port_selection": {
    "default": {
      "prefer": ["APC40 mkII"]
    }
  },
  "output_port_selection": {
    "default": {
      "prefer": ["APC40 mkII"]
    }
  },
  "devices": [
    {
      "model": "APC40 MK2",
      "detection_patterns": ["APC40 mkII"]
    }
  ]
}
```

### Step 4: DONE!

**No changes needed to**:
- DeviceController
- DeviceRegistry
- GenericDevice
- GenericInput
- Your application code

The registry automatically:
1. Detects "APC40 mkII" in USB device list
2. Loads config from devices.json
3. Creates APC40Mapper and APC40Output
4. Wraps in GenericDevice
5. Returns to DeviceController

**Your app just works with the new device!**

---

## 🎓 Why This Design is Brilliant

### 1. **Separation of Concerns**

```
DeviceController:    "I manage connections and notify users"
DeviceRegistry:         "I build the right device from parts"
Implementations:        "I know hardware-specific details"
Config:                 "I store device data"
```

No component does more than one job.

### 2. **Open/Closed Principle**

- **Open for extension**: Add new devices without modifying existing code
- **Closed for modification**: Core logic never changes

### 3. **Dependency Inversion**

```
High-level:  DeviceController
               ↓ depends on
             Device Protocol (abstract)
               ↑ implements
Low-level:   LaunchpadMK3Output (concrete)
```

The application depends on abstractions, not concrete adapters.

### 4. **Single Source of Truth**

- Device capabilities? → `devices.json`
- Note mapping? → `LaunchpadMK3Mapper`
- LED colors? → `ui_colors.py`
- Port selection? → `config.py`

No duplication anywhere.

### 5. **Testability**

Every component can be tested in isolation:

```python
# Test mapper independently
def test_note_mapping():
    mapper = LaunchpadMK3Mapper(config)
    assert mapper.note_to_index(11) == 0   # Bottom-left
    assert mapper.note_to_index(36) == 21  # Row 2, col 5

# Test input parsing with mock mapper
def test_input_parsing():
    mock_mapper = MockMapper()
    input_handler = GenericInput(mock_mapper)
    event = input_handler.parse_message(note_on_msg)
    assert isinstance(event, PadPressEvent)

# Test registry with mock config
def test_device_detection():
    registry = DeviceRegistry()
    config = registry.detect_device("LPProMK3 MIDI")
    assert config.family == "launchpad_mk3"
```

---

## 📊 Data Flow Summary

### Incoming (Button Press)

```
Hardware → MIDI Message → GenericInput → Mapper → PadPressEvent → Observer → Your Code
```

### Outgoing (LED Control)

```
Your Code → DeviceController → Output → Mapper → SysEx → MIDI Message → Hardware
```

### Device Detection

```
USB Connect → MidiManager → Registry.detect_device() → devices.json → DeviceConfig
```

### Device Creation

```
DeviceConfig → Registry.create_device() → get_implementation() → Mapper + Output → GenericDevice
```

---

## 🔍 How to Navigate the Code

**Start here if you want to**:

1. **Understand how a button press becomes an event**:
   - Read [input.py](src/launchsampler/devices/input.py) (79 lines, very simple)
   - Then [adapters/launchpad_mk3.py](src/launchsampler/devices/adapters/launchpad_mk3.py) lines 14-110 (mapper)

2. **Understand how LEDs are controlled**:
   - Read [adapters/launchpad_sysex.py](src/launchsampler/devices/adapters/launchpad_sysex.py) (59 lines)
   - Then [adapters/launchpad_mk3.py](src/launchsampler/devices/adapters/launchpad_mk3.py) lines 113-310 (output)

3. **Understand device detection**:
   - Read [config.py](src/launchsampler/devices/config.py) (169 lines, port selection logic)
   - Then [registry.py](src/launchsampler/devices/registry.py) (203 lines, factory pattern)

4. **Understand the user API**:
   - Read [launchpad/controller.py](src/launchsampler/devices/launchpad/controller.py) (312 lines)

5. **Understand protocols (contracts)**:
   - Read [protocols.py](src/launchsampler/devices/protocols.py) (93 lines, all interfaces)

---

## 🎯 The Bottom Line

This architecture transforms a messy hardware problem into a clean, extensible system:

**Without this design**:
```python
if device_name == "Launchpad Pro":
    if sys.platform == "win32":
        port = "LPProMK3 MIDI 0"
    else:
        port = "Launchpad Pro MK3"
    # Hardcoded note mapping
    if note == 11:
        return 0
    elif note == 12:
        return 1
    # ... 100 more if statements
```

**With this design**:
```python
controller = DeviceController()
controller.start()
controller.set_pad_color(21, Color(255, 0, 0))
# Works with ANY supported device!
```

The registry handles all the complexity **declaratively** (via JSON config) instead of **imperatively** (via if/else chains).

---

## 🎨 Visual Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAUNCHPAD CONTROLLER                         │
│                   (User-Friendly Remote)                        │
│                                                                 │
│   "I don't care what device you have, just give me buttons     │
│    and LEDs in logical indices 0-63"                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Uses
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                     DEVICE REGISTRY                             │
│                   (The Smart Factory)                           │
│                                                                 │
│   "I read devices.json and build the right device for          │
│    whatever hardware you plug in"                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴─────────────┬─────────────┐
          ↓                            ↓             ↓
┌──────────────────┐         ┌──────────────┐  ┌──────────────┐
│  devices.json    │         │ Mapper       │  │ Output       │
│  (Config)        │         │ (Translation)│  │ (LED Control)│
└──────────────────┘         └──────────────┘  └──────────────┘
          │                            │             │
          │                            └──────┬──────┘
          │                                   │
          │                        Assembled into
          │                                   ↓
          │                        ┌──────────────────┐
          │                        │ GenericDevice    │
          │                        │ (Complete Unit)  │
          │                        └──────────────────┘
          │
          └─→ Points to implementation: "LaunchpadMK3"
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                  IMPLEMENTATIONS FOLDER                         │
│              (Hardware-Specific Brains)                         │
│                                                                 │
│   LaunchpadMK3Mapper:  "Note 11 = index 0, note 36 = index 21" │
│   LaunchpadMK3Output:  "To light LED, send this SysEx"         │
│   LaunchpadSysEx:      "Header = [0, 32, 41, 2, 14]"           │
└─────────────────────────────────────────────────────────────────┘
```

**The genius**: Each layer knows **nothing** about the layers above it, but provides a clean interface for them to use. Add a new device by adding a new implementation + JSON config, no changes to the registry or controller needed.
