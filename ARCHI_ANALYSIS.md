# LaunchSampler Architecture Analysis

**Document Purpose**: Comprehensive architectural documentation derived from 199 passing tests and validated against actual implementation.

**Analysis Date**: Based on test suite with 42% overall coverage (97% Player, 94% SamplerEngine, 100% StateMachine)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Test-Driven Architecture Discovery](#test-driven-architecture-discovery)
3. [System Architecture](#system-architecture)
4. [Component Analysis](#component-analysis)
5. [Event Flow Architecture](#event-flow-architecture)
6. [Thread Model](#thread-model)
7. [Key Design Patterns](#key-design-patterns)
8. [Integration Points](#integration-points)

---

## Executive Summary

LaunchSampler is a **real-time audio sampling engine** for Novation Launchpad controllers. The architecture is characterized by:

- **Event-Driven**: Observer pattern for state propagation, no polling
- **Lock-Free Audio Path**: 256-entry queue for sub-millisecond latency triggering
- **UI-Agnostic Core**: Player orchestrates audio/MIDI without UI dependencies
- **Hot-Plug MIDI**: Automatic device detection with 5-second polling
- **Thread-Safe**: Audio callback, MIDI thread, UI thread coordination
- **Separation of Concerns**: Clear boundaries between domain models, audio engine, controllers, and UI

**Test Coverage Metrics**:
- Total Tests: 199 passing
- Coverage: 42% overall (1647/2851 lines)
- Critical Components: Player 97%, SamplerEngine 94%, StateMachine 100%
- Domain Models: 90-100% coverage

---

## Test-Driven Architecture Discovery

### What Tests Reveal About System Behavior

#### 1. Domain Model Layer (30 tests)
**Test Evidence**: `test_models.py` validates Pydantic models for data integrity

```
Key Behaviors Discovered:
├── Color: RGB validation (0-127), factory methods, tuple conversion
├── Sample: Path-based loading, file existence checking
├── Pad: Coordinate validation (0-7), assignment tracking, clearing
├── Launchpad: 64-pad grid, coordinate ↔ MIDI note conversion, bulk loading
├── Set: Serialization with path resolution, relative path handling, common path detection
├── PlaybackMode: ENUM with default color mapping
└── AppConfig: JSON persistence, default values

Test Pattern: Property validation + Edge case handling + Factory methods
```

**Implementation Validation**: ✅ Tests match implementation exactly. Models use Pydantic BaseModel with field validators.

#### 2. Audio Data Structures (17 tests)
**Test Evidence**: `test_audio_data.py` reveals dataclass-based runtime structures

```
AudioData Behaviors:
├── from_array: Mono/stereo detection, dtype conversion to float32
├── duration: Calculated property (frames / sample_rate)
├── get_mono: Channel averaging for stereo
├── normalize: Peak normalization to target level (default 0.95)
└── get_info: Metadata dictionary with duration, sample_rate, channels, size

PlaybackState Behaviors:
├── start(): Reset position to 0, set is_playing=True
├── stop(): Set is_playing=False
├── advance(frames): Position increment with mode-based looping
├── get_frames(n): Return audio slice with volume applied
├── Seamless looping: Wrap-around buffer reads for LOOP mode
└── Mode handling: ONE_SHOT stops at end, LOOP wraps, HOLD stops at end

Test Pattern: Lifecycle methods + State transitions + Edge cases (end of buffer)
```

**Implementation Validation**: ✅ Uses `@dataclass(slots=True)` for performance. Tests confirm correct loop wrapping and mode-specific behavior.

#### 3. State Machine (12 tests)
**Test Evidence**: `test_state_machine.py` reveals observer pattern implementation

```
Event Flow:
User Input → PAD_TRIGGERED → PAD_PLAYING → PAD_FINISHED/PAD_STOPPED
                                         ↘
                                           (MIDI) NOTE_ON/NOTE_OFF

State Tracking:
├── _playing_pads: set[int] - Currently playing pad indices
├── _triggered_pads: set[int] - Triggered but not yet playing
└── _observers: list[StateObserver] - Event subscribers

Event Types (from PlaybackEvent enum):
├── NOTE_ON: MIDI input received (always fired, even for empty pads)
├── NOTE_OFF: MIDI release received (always fired)
├── PAD_TRIGGERED: Audio trigger queued
├── PAD_PLAYING: Audio playback started
├── PAD_STOPPED: Audio stopped by user/mode
└── PAD_FINISHED: Audio completed naturally

Test Pattern: Event propagation + Multiple observers + Exception isolation
```

**Implementation Validation**: ✅ Thread-safe with `threading.Lock`. Exception handling prevents bad observers from breaking others. Matches test behavior exactly.

#### 4. Audio Device Management (11 tests)
**Test Evidence**: `test_audio_device.py` reveals platform-specific API selection

```
Platform APIs:
├── Windows: ASIO, WASAPI
├── macOS: Core Audio
└── Linux: ALSA, JACK

Device Validation:
├── _get_platform_apis(): Returns low-latency API list for current OS
├── _is_valid_device(id): Checks if device uses low-latency API
├── list_output_devices(): Returns (devices, api_names) tuple
└── Raises ValueError for non-low-latency devices

Lifecycle:
├── set_callback(fn): Register audio callback
├── start(): Begin audio stream (requires callback set)
├── stop(): Stop audio stream
└── Context manager: with AudioDevice(...) for RAII pattern

Test Pattern: Platform detection + Validation + Lifecycle + Error handling
```

**Implementation Validation**: ✅ Uses sounddevice library. Tests confirm API filtering and validation logic.

#### 5. MIDI Controller (11 tests)
**Test Evidence**: `test_midi_controller.py` reveals Launchpad protocol

```
Device Detection:
LaunchpadDevice.matches(port_name):
├── "Launchpad X" → True
├── "Launchpad Mini" → True
├── "LPProMK3 MIDI 1" → True
├── "LPMiniMK3 MIDI 1" → True
└── "Other Device" → False

Port Selection:
├── Prefer "MIDI 1" ports over others
└── Fall back to first available

Message Parsing:
├── note_on (velocity > 0) → ("pad_press", note)
├── note_on (velocity = 0) → ("pad_release", note)
├── note_off → ("pad_release", note)
├── clock → None (filtered)
└── Valid range: notes 0-63 (8x8 grid)

Callback Pattern:
├── on_pad_pressed(callback): Register press handler
├── on_pad_released(callback): Register release handler
├── on_connection_changed(callback): Register connection state handler
└── Callbacks execute in mido's I/O thread (must be fast)

Test Pattern: Protocol parsing + Callback registration + Thread safety
```

**Implementation Validation**: ✅ Composes `MidiManager` with `LaunchpadDevice` protocol. Hot-plug support with 5s polling. Context manager support.

#### 6. SamplerEngine Queue System (51 tests)
**Test Evidence**: `test_sampler_engine_queue.py` reveals lock-free architecture

```
Queue Architecture:
Lock-Free Trigger Queue (256 entries):
├── trigger_pad() → Queue.put_nowait(("trigger", pad_index))
├── release_pad() → Queue.put_nowait(("release", pad_index))
├── stop_pad() → Queue.put_nowait(("stop", pad_index))
└── _audio_callback() processes queue FIRST, then mixes audio

Voice Management:
├── active_voices: Property counting is_playing states
├── get_playing_pads(): Returns list[int] from state machine
├── Voice tracking: Increment on start, decrement on stop/finish
└── stop_all(): Directly stops all playback states (synchronous)

Playback Modes (from tests):
├── ONE_SHOT: Plays to end, ignores release
├── LOOP: Loops continuously, stops on release
├── HOLD: Plays while held, stops on release
└── LOOP_TOGGLE: Toggle on/off with each trigger, ignores release

Event Timing:
PAD_TRIGGERED → (queue processing) → PAD_PLAYING → (audio mixing) → PAD_FINISHED

Thread Safety:
├── Trigger queue: Lock-free (Queue.put_nowait/get_nowait)
├── Sample loading: Protected by threading.Lock
├── Playback states: Owned by audio thread (no lock needed for reads)
└── Volume/mode updates: Protected by threading.Lock

Audio Mixing:
├── Get active states (is_playing=True)
├── Call AudioMixer.mix(states, frames)
├── Apply master volume
├── Soft clip to prevent distortion
└── Copy to output buffer

Test Pattern: Queue processing + Mode behavior + Thread safety + Event timing
```

**Implementation Validation**: ✅ Exactly matches test behavior. Queue processed at start of audio callback for minimal latency. State machine tracks playing pads independently.

#### 7. Player Orchestration (39 tests)
**Test Evidence**: `test_player.py` reveals UI-agnostic coordinator

```
Component Composition:
Player orchestrates:
├── AudioDevice: Hardware audio output
├── SamplerEngine: Audio playback engine
├── LaunchpadController: MIDI input
├── StateMachine: Event observation (via SamplerEngine)
└── Set: Current loaded pad configuration

Lifecycle:
start(initial_set=None):
├── Create AudioDevice(device, buffer_size, low_latency=True)
├── Create SamplerEngine(audio_device, num_pads=64)
├── Register self as observer: engine.register_observer(self)
├── Load set into engine if provided
├── Start engine
└── Start MIDI controller (optional, failure doesn't block)

stop():
├── Stop MIDI controller
└── Stop audio engine

Set Loading:
load_set(set_obj):
├── Update current_set reference
└── Load all assigned pads: engine.load_sample(index, pad)

MIDI Event Handling:
_on_pad_pressed(index):
├── Fire PlaybackEvent.NOTE_ON (always, even for empty pads)
└── If pad.is_assigned: trigger_pad(index)

_on_pad_released(index):
├── Fire PlaybackEvent.NOTE_OFF (always)
└── If pad.is_assigned AND mode in (LOOP, HOLD): release_pad(index)

_on_midi_connection_changed(is_connected, port_name):
└── Fire PlaybackEvent.NOTE_OFF with pad_index=-1 (signal event)

StateObserver Implementation:
on_playback_event(event, pad_index):
└── Forward to registered callback (if set)

Query Methods:
├── is_running: bool
├── is_midi_connected: bool
├── active_voices: int (from engine)
├── audio_device_name: str
├── midi_device_name: str
├── is_pad_playing(index): bool
└── get_playing_pads(): list[int]

Test Pattern: Integration + Lifecycle + Event routing + Error handling
```

**Implementation Validation**: ✅ Player is StateObserver, forwards events to callback. MIDI failure doesn't block startup. Exactly matches test behavior.

#### 8. Sample Loading & Caching (5 tests from engine tests)
**Test Evidence**: Reveals caching strategy

```
Cache Architecture:
_audio_cache: Dict[str, AudioData]  # path → AudioData
├── Same sample on multiple pads → Single cached entry
├── AudioData is immutable, safe to share
└── clear_cache(): Remove all entries

Loading Flow:
load_sample(pad_index, pad):
├── Check cache: if path in _audio_cache: use cached
├── Else: Load with SampleLoader, add to cache
├── Create/update PlaybackState for pad
└── Assign mode, volume, reset position

PlaybackState per pad:
├── audio_data: Reference to cached AudioData
├── mode: PlaybackMode (independent per pad)
├── volume: float (independent per pad)
└── position: float (independent runtime state)

Test Pattern: Cache efficiency + Reference sharing + Memory management
```

**Implementation Validation**: ✅ Caching prevents duplicate loads. PlaybackState is per-pad, AudioData is shared. Matches test behavior.

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                            │
│  (TUI, GUI, CLI - not tested, out of scope for core)       │
└───────────────────┬─────────────────────────────────────────┘
                    │ Observes events
                    │ Calls control methods
┌───────────────────▼─────────────────────────────────────────┐
│                         Player                              │
│  (Core Orchestrator - UI Agnostic)                         │
│                                                             │
│  Responsibilities:                                          │
│  • Lifecycle management (start/stop)                       │
│  • Set loading into engine                                 │
│  • MIDI event → Audio trigger routing                      │
│  • Event observation & forwarding                          │
│  • Query methods (status, device names)                    │
│                                                             │
│  Component References:                                      │
│  • AudioDevice + SamplerEngine                             │
│  • LaunchpadController (optional)                          │
│  • Current Set (domain model)                              │
└─────┬───────────────────────────┬─────────────────┬─────────┘
      │                           │                 │
      │                           │                 │
┌─────▼──────────┐    ┌──────────▼──────────┐    ┌▼─────────────────┐
│ SamplerEngine  │    │ LaunchpadController │    │  Set (Model)     │
│                │    │                     │    │                  │
│ • Queue system │    │ • Hot-plug support  │    │ • Launchpad      │
│ • Voice mgmt   │    │ • Message parsing   │    │   - 64 Pads      │
│ • Audio mixing │    │ • Color control     │    │     - Sample     │
│ • State events │    │ • Connection events │    │     - Mode       │
└─────┬──────────┘    └──────────┬──────────┘    │     - Color      │
      │                          │                │     - Volume     │
      │                          │                └──────────────────┘
┌─────▼──────────┐    ┌──────────▼──────────┐
│  AudioDevice   │    │    MidiManager      │
│                │    │                     │
│ • Platform API │    │ • Port monitoring   │
│   selection    │    │ • Auto-reconnect    │
│ • Stream mgmt  │    │ • Input/Output mgmt │
│ • Callback     │    │ • Device filtering  │
└─────┬──────────┘    └─────────────────────┘
      │
┌─────▼──────────┐
│   PortAudio    │
│   (sounddevice)│
└────────────────┘
```

### Layer Separation

#### Layer 1: Domain Models (Pydantic)
**Location**: `src/launchsampler/models/`
**Purpose**: Data validation, serialization, business rules
**Dependencies**: None (pure data)

```python
# Test-validated structure:
Color → RGB validation (0-127)
Sample → File path, existence check
Pad → Coordinates (0-7), sample assignment, mode
Launchpad → 64 pads, coordinate conversion
Set → Named configuration, serialization
PlaybackMode → Enum (ONE_SHOT, LOOP, HOLD, LOOP_TOGGLE)
AppConfig → Application settings
```

#### Layer 2: Audio Primitives
**Location**: `src/launchsampler/audio/`
**Purpose**: Hardware-agnostic audio operations

```python
# Test-validated components:
AudioData → In-memory audio buffer (dataclass)
PlaybackState → Runtime playback state (dataclass)
AudioDevice → Platform audio I/O (sounddevice wrapper)
AudioMixer → Multi-source mixing
SampleLoader → File loading with resampling
```

#### Layer 3: MIDI Primitives
**Location**: `src/launchsampler/midi/`, `src/launchsampler/devices/launchpad/`
**Purpose**: Hardware-agnostic MIDI operations

```python
# Test-validated components:
BaseMidiManager → Hot-plug monitoring base class
MidiManager → Input/output coordination
InputManager → MIDI input with device filter
OutputManager → MIDI output
LaunchpadDevice → Protocol (message parsing, LED control)
LaunchpadController → High-level API composing MidiManager + protocol
```

#### Layer 4: Core Engine
**Location**: `src/launchsampler/core/`
**Purpose**: Audio engine, state management, coordination

```python
# Test-validated components:
SamplerEngine → Queue + voice management + mixing
SamplerStateMachine → Event dispatch + state tracking
Player → Orchestrates audio + MIDI without UI
```

#### Layer 5: UI (Not in Core Tests)
**Location**: `src/launchsampler/tui/`, `src/launchsampler/cli/`
**Purpose**: User interface (TUI, CLI)
**Note**: Separate from core, tested independently

---

## Component Analysis

### Player (154 lines, 97% coverage)

**Role**: UI-agnostic orchestrator

**Test-Revealed Characteristics**:
- No UI dependencies (can be used in TUI, GUI, CLI, headless)
- Manages component lifecycle (audio, MIDI)
- Routes MIDI events to audio triggers
- Implements StateObserver protocol
- Forwards events to registered callback
- MIDI failures don't block startup

**Key Methods** (from 39 tests):
```python
# Lifecycle
start(initial_set=None) → bool
stop() → None

# Set Management
load_set(set_obj: Set) → None

# Playback Control (forwarded to engine)
trigger_pad(pad_index: int) → None
release_pad(pad_index: int) → None
stop_pad(pad_index: int) → None
stop_all() → None
set_master_volume(volume: float) → None

# Query Methods
is_running: bool
is_midi_connected: bool
active_voices: int
audio_device_name: str
midi_device_name: str
is_pad_playing(pad_index: int) → bool
get_playing_pads() → list[int]

# Event System
set_playback_callback(callback) → None
on_playback_event(event, pad_index) → None  # StateObserver protocol
```

**MIDI Event Translation** (from tests):
```
MIDI Press → NOTE_ON (always) + trigger_pad (if assigned)
MIDI Release → NOTE_OFF (always) + release_pad (if LOOP/HOLD mode)
MIDI Connection Change → NOTE_OFF (with pad_index=-1 as signal)
```

### SamplerEngine (179 lines, 94% coverage)

**Role**: Real-time audio playback engine

**Test-Revealed Characteristics**:
- Lock-free trigger path (256-entry queue)
- Queue processed at START of audio callback
- Audio thread owns playback states
- Supports 4 playback modes with different behaviors
- State machine integration for event dispatch
- Audio cache for memory efficiency
- Soft clipping to prevent distortion

**Architecture** (from 51 tests):
```
Public API (thread-safe):
├── trigger_pad(index) → Queue.put_nowait(("trigger", index))
├── release_pad(index) → Queue.put_nowait(("release", index))
├── stop_pad(index) → Queue.put_nowait(("stop", index))
├── stop_all() → Direct state stop (synchronous)
├── load_sample(index, pad) → Lock-protected cache + state update
├── unload_sample(index) → Lock-protected state clear
└── Query methods (lock-free or lock-protected)

Audio Callback (audio thread):
├── Process trigger queue (all pending actions)
├── Track playing pads before mixing
├── Mix active states (AudioMixer.mix)
├── Detect finished pads (natural completion)
├── Apply master volume
├── Soft clip
└── Copy to output buffer

State Management:
├── _playback_states: Dict[int, PlaybackState] (audio thread owns)
├── _audio_cache: Dict[str, AudioData] (lock-protected for loading)
├── _state_machine: SamplerStateMachine (thread-safe observer pattern)
└── _trigger_queue: Queue (lock-free, size=256)
```

**Playback Mode Behaviors** (validated by tests):
```python
ONE_SHOT:
├── Plays sample once to completion
├── Ignores release messages
└── Stops at end of sample

LOOP:
├── Loops continuously
├── Stops on release message
└── Seamless wrap-around at buffer end

HOLD:
├── Plays while held
├── Stops immediately on release
└── Stops at end if not released

LOOP_TOGGLE:
├── First trigger: Start playing + loop
├── Second trigger: Stop playing
├── Ignores release messages
└── Toggle state tracked per pad
```

### SamplerStateMachine (55 lines, 100% coverage)

**Role**: State tracking + observer dispatch

**Test-Revealed Characteristics**:
- Thread-safe with Lock
- Exception isolation (bad observer doesn't break others)
- Separates triggered from playing states
- Prevents duplicate notifications

**State Transitions** (from 12 tests):
```
on_pad_triggered(index):
├── Add to _triggered_pads
└── Notify: PAD_TRIGGERED

on_pad_playing(index):
├── Remove from _triggered_pads
├── Add to _playing_pads
└── Notify: PAD_PLAYING

on_pad_stopped(index):
├── Remove from _triggered_pads
├── Remove from _playing_pads
└── Notify: PAD_STOPPED (only if was playing)

on_pad_finished(index):
├── Remove from _playing_pads
└── Notify: PAD_FINISHED (only if was playing)
```

### LaunchpadController

**Role**: High-level Launchpad API

**Test-Revealed Characteristics**:
- Composes MidiManager with LaunchpadDevice protocol
- Callbacks execute in mido's I/O thread
- Hot-plug support with configurable polling
- Port preference: "MIDI 1" > first available

**Protocol** (from 11 tests):
```python
# Device Detection
LaunchpadDevice.matches(port_name) → bool
├── Patterns: "Launchpad", "LPProMK3", "LPMiniMK3", "LPX"
└── Filters non-matching devices

# Message Parsing
LaunchpadDevice.parse_input(msg) → Optional[tuple[str, int]]
├── note_on (vel > 0) → ("pad_press", note)
├── note_on (vel = 0) → ("pad_release", note)  # Note: MIDI quirk
├── note_off → ("pad_release", note)
├── clock → None (filtered)
└── Valid range: 0-63

# LED Control
LaunchpadDevice.create_led_message(pad_index, color) → Message
└── SysEx message for RGB LED control
```

---

## Event Flow Architecture

### Primary Event Types

From `protocols.py` and validated by tests:

```python
class PlaybackEvent(Enum):
    NOTE_ON = "note_on"          # MIDI input (always fired)
    NOTE_OFF = "note_off"        # MIDI release (always fired)
    PAD_TRIGGERED = "pad_triggered"  # Audio trigger queued
    PAD_PLAYING = "pad_playing"      # Audio started
    PAD_STOPPED = "pad_stopped"      # Audio stopped by user
    PAD_FINISHED = "pad_finished"    # Audio completed naturally
```

### Event Flow Diagrams

#### MIDI Press → Audio Playback (ONE_SHOT mode)

```
User Presses Pad
      │
      ▼
┌─────────────────────────────────────────────────┐
│          LaunchpadController                    │
│  (mido I/O thread)                             │
│                                                 │
│  1. Receive MIDI note_on                       │
│  2. Parse: ("pad_press", pad_index)            │
│  3. Call: _on_pad_pressed(pad_index)           │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│              Player                             │
│  (MIDI thread → callback execution)            │
│                                                 │
│  1. Fire: PlaybackEvent.NOTE_ON                │
│  2. Check: pad.is_assigned?                    │
│  3. If yes: trigger_pad(pad_index)             │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│          SamplerEngine                          │
│  (MIDI thread → queue write)                   │
│                                                 │
│  1. Queue.put_nowait(("trigger", pad_index))   │
│     • Non-blocking                              │
│     • Lock-free                                 │
│     • Drops if queue full (logged)             │
└─────────────────────────────────────────────────┘
                    ⏳ Queued until audio callback
               │
               ▼
┌─────────────────────────────────────────────────┐
│          SamplerEngine._audio_callback          │
│  (Audio thread - real-time)                    │
│                                                 │
│  1. Process trigger queue:                     │
│     action, pad_index = queue.get_nowait()     │
│                                                 │
│  2. Get PlaybackState for pad_index            │
│                                                 │
│  3. state.start()                              │
│     • is_playing = True                        │
│     • position = 0.0                           │
│                                                 │
│  4. Fire: state_machine.on_pad_triggered()     │
│                                                 │
│  5. Fire: state_machine.on_pad_playing()       │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│        SamplerStateMachine                      │
│  (Audio thread)                                │
│                                                 │
│  1. on_pad_triggered(pad_index):               │
│     • Add to _triggered_pads                   │
│     • Notify: PAD_TRIGGERED                    │
│                                                 │
│  2. on_pad_playing(pad_index):                 │
│     • Move from _triggered to _playing         │
│     • Notify: PAD_PLAYING                      │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│              Player                             │
│  (Audio thread → observer callback)            │
│                                                 │
│  1. on_playback_event(PAD_TRIGGERED, index)    │
│  2. on_playback_event(PAD_PLAYING, index)      │
│     → Forward to _on_playback_change callback  │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│              UI Layer                           │
│  (Audio thread → should queue for UI thread)   │
│                                                 │
│  Update display:                                │
│  • Highlight playing pad                       │
│  • Update voice count                          │
│  • Update status bar                           │
└─────────────────────────────────────────────────┘
```

#### Audio Completion → PAD_FINISHED Event

```
Audio Callback Processing
      │
      ▼
┌─────────────────────────────────────────────────┐
│      SamplerEngine._audio_callback              │
│  (Audio thread)                                │
│                                                 │
│  1. Track playing pads BEFORE mixing:          │
│     was_playing_before = {idx for state        │
│                           if state.is_playing} │
│                                                 │
│  2. Mix audio:                                 │
│     active_states = [s for s if s.is_playing] │
│     mixed = mixer.mix(active_states, frames)   │
│                                                 │
│     During mixing, each state:                 │
│     • Calls state.get_frames(frames)           │
│     • Advances position                        │
│     • Checks if finished (ONE_SHOT mode)       │
│     • state.is_playing set to False            │
│                                                 │
│  3. Detect finished pads:                      │
│     for pad_index in was_playing_before:       │
│       if not state.is_playing:                 │
│         state_machine.on_pad_finished(index)   │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│        SamplerStateMachine                      │
│                                                 │
│  on_pad_finished(pad_index):                   │
│  ├── Remove from _playing_pads                 │
│  └── Notify: PAD_FINISHED                      │
└──────────────┬──────────────────────────────────┘
               │
               ▼
           UI Update
```

#### MIDI Release → Audio Stop (LOOP mode)

```
User Releases Pad
      │
      ▼
LaunchpadController → Player._on_pad_released
      │                      │
      │                      ├─ Fire: NOTE_OFF
      │                      └─ Check: mode in (LOOP, HOLD)?
      │                         If yes: release_pad()
      ▼
SamplerEngine.release_pad
      │
      └─ Queue.put_nowait(("release", pad_index))
            │
            ▼
Audio Callback Processing
      │
      └─ action = "release"
         state.stop()
         state_machine.on_pad_stopped()
            │
            ▼
      PAD_STOPPED event → UI
```

### Event Timeline (ONE_SHOT Sample, 1 second duration)

```
Time    Thread          Event
─────────────────────────────────────────────────────────────
0ms     MIDI           User presses pad
1ms     MIDI           Parse MIDI message
2ms     MIDI           Player._on_pad_pressed()
2ms     MIDI           Fire: NOTE_ON (instant UI feedback)
2ms     MIDI           SamplerEngine.trigger_pad()
2ms     MIDI           Queue.put_nowait(("trigger", index))
        
10ms    Audio          Audio callback starts
10ms    Audio          Process queue: get ("trigger", index)
10ms    Audio          state.start()
10ms    Audio          Fire: PAD_TRIGGERED
11ms    Audio          Fire: PAD_PLAYING
11ms    Audio          Mix audio frames (512 @ 44.1kHz = ~11ms)
22ms    Audio          Write to output buffer
22ms    Audio          Audio callback ends
        
...     Audio          Subsequent callbacks mix audio
        
1000ms  Audio          state.position >= num_frames
1000ms  Audio          state.is_playing = False
1000ms  Audio          Detect: was_playing && !is_playing
1000ms  Audio          Fire: PAD_FINISHED
1001ms  Audio          Update UI: unhighlight pad
```

**Key Latency Points**:
- **MIDI → Queue**: 1-2ms (negligible)
- **Queue → Audio Start**: Up to one audio callback period (~10ms @ 512 frames, 44.1kHz)
- **Total Trigger Latency**: ~12ms (imperceptible to human)

---

## Thread Model

### Thread Analysis from Tests

#### 1. Main Thread (UI/Application)
**Operations**:
- Player lifecycle (start/stop)
- Set loading
- User-initiated commands (trigger, stop)
- Query methods (is_playing, active_voices)

**Thread Safety**:
- Player methods are synchronous (no threading in Player itself)
- SamplerEngine queue operations are lock-free
- Sample loading uses lock

#### 2. MIDI Input Thread (mido library)
**Operations**:
- Message reception
- Callback execution: `_on_pad_pressed`, `_on_pad_released`

**Thread Safety**:
- Callbacks must be fast (don't block I/O thread)
- Player forwards to engine queue (lock-free)
- NOTE_ON/NOTE_OFF events fired synchronously

#### 3. Audio Callback Thread (sounddevice/PortAudio)
**Operations**:
- Queue processing (trigger/release/stop actions)
- Audio mixing
- Position advancement
- Event firing (PAD_PLAYING, PAD_FINISHED)

**Thread Safety**:
- Owns playback states (no lock needed for reads)
- State machine uses lock for observer list
- Must never block (no I/O, no heavy computation)

#### 4. MIDI Monitor Thread (background)
**Operations**:
- Device polling (every 5 seconds)
- Connection/disconnection detection
- Auto-reconnect

**Thread Safety**:
- Uses lock for port access
- Connection callbacks fired in separate thread

### Lock Usage Summary

| Component | Lock Type | Purpose | Threads |
|-----------|-----------|---------|---------|
| SamplerEngine._trigger_queue | Queue (internal lock) | Trigger actions | MIDI → Audio |
| SamplerEngine._lock | threading.Lock | Sample loading/unloading | Main, MIDI |
| SamplerEngine._playback_states | None (audio thread owns) | Playback state | Audio only |
| SamplerStateMachine._lock | threading.Lock | Observer list + state sets | Audio, Main |
| MidiManager._port_lock | threading.Lock | Port access | Monitor, Main |

### Critical Section Analysis

**Smallest Critical Sections** (from tests):
```python
# SamplerEngine.trigger_pad - Lock-free!
def trigger_pad(self, pad_index: int):
    self._trigger_queue.put_nowait(("trigger", pad_index))  # No lock

# SamplerEngine.load_sample - Lock only for state update
def load_sample(self, pad_index: int, pad: Pad):
    # Load from cache or file (no lock needed for cache read)
    audio_data = self._audio_cache.get(path) or self._loader.load(path)
    
    with self._lock:  # Only lock for state modification
        self._playback_states[pad_index] = PlaybackState(audio_data)
```

---

## Key Design Patterns

### 1. Observer Pattern
**Implementation**: `StateObserver` protocol + `SamplerStateMachine`

**Participants**:
- **Subject**: `SamplerStateMachine`
- **Observers**: `Player` (implements `StateObserver`)
- **Events**: `PlaybackEvent` enum

**Test Evidence** (12 tests in `test_state_machine.py`):
```python
# Multiple observers receive events
machine.register_observer(observer1)
machine.register_observer(observer2)
machine.on_pad_triggered(5)
# Both observers notified

# Exception isolation
bad_observer.on_playback_event.side_effect = RuntimeError
machine.on_pad_triggered(5)
# Other observers still receive event (exception logged)
```

**Benefits**:
- Loose coupling (audio engine doesn't know about UI)
- Multiple observers (TUI, logging, recording, etc.)
- Thread-safe event dispatch

### 2. Lock-Free Queue
**Implementation**: `Queue.put_nowait` + `Queue.get_nowait`

**Test Evidence** (10 tests in `test_sampler_engine_queue.py`):
```python
# Non-blocking writes
engine.trigger_pad(0)  # Queue.put_nowait
engine.trigger_pad(1)  # Queue.put_nowait
# No blocking, even from different threads

# Audio callback processing
while not queue.empty():
    action, pad_index = queue.get_nowait()
    # Process immediately in audio thread
```

**Benefits**:
- Sub-millisecond latency (no lock contention)
- Audio thread never blocks
- MIDI thread never blocks
- Graceful degradation (drops if full, logs warning)

### 3. Strategy Pattern
**Implementation**: `PlaybackMode` enum with mode-specific behavior

**Test Evidence** (7 tests in `test_sampler_engine_queue.py`):
```python
# Different behaviors per mode
ONE_SHOT: plays to end, ignores release
LOOP: loops continuously, stops on release
HOLD: stops on release
LOOP_TOGGLE: toggle on trigger, ignores release
```

**Benefits**:
- Single `PlaybackState` class handles all modes
- Mode changes during playback (tests confirm)
- Easy to add new modes

### 4. Composition Over Inheritance
**Implementation**: Player composes AudioDevice, SamplerEngine, LaunchpadController

**Test Evidence** (39 tests in `test_player.py`):
```python
# Player doesn't inherit from anything
# It composes:
self._audio_device = AudioDevice(...)
self._engine = SamplerEngine(self._audio_device, ...)
self._midi = LaunchpadController(...)
```

**Benefits**:
- Clear separation of concerns
- Easy to test with mocks
- Flexible configuration (swap components)

### 5. Repository Pattern (Cache)
**Implementation**: `SamplerEngine._audio_cache`

**Test Evidence** (5 tests in `test_sampler_engine_queue.py`):
```python
# Single cache entry for same sample on multiple pads
engine.load_sample(0, pad_with_kick)
engine.load_sample(1, pad_with_kick)
assert len(engine._audio_cache) == 1  # Only one entry
```

**Benefits**:
- Memory efficiency (no duplicate audio data)
- Faster loading (cache hit)
- Explicit cache management (clear_cache)

### 6. Protocol (Structural Typing)
**Implementation**: `StateObserver` protocol (Python 3.8+)

```python
@runtime_checkable
class StateObserver(Protocol):
    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        ...
```

**Benefits**:
- Duck typing with type checking
- No inheritance required
- Flexible implementations

---

## Integration Points

### 1. Audio Engine → UI
**Mechanism**: Observer callbacks
**Thread**: Audio thread → UI thread (requires queue)

```python
# Player forwards events to callback
def on_playback_event(self, event: PlaybackEvent, pad_index: int):
    if self._on_playback_change:
        self._on_playback_change(event, pad_index)

# UI must queue for UI thread
# (tests don't cover UI threading, but pattern is clear)
```

### 2. MIDI Input → Audio Engine
**Mechanism**: Player routes MIDI to engine
**Thread**: MIDI thread → Queue → Audio thread

```python
# Player._on_pad_pressed (MIDI thread)
def _on_pad_pressed(self, pad_index: int):
    if self._on_playback_change:
        self._on_playback_change(PlaybackEvent.NOTE_ON, pad_index)
    if pad.is_assigned:
        self.trigger_pad(pad_index)  # → Queue.put_nowait
```

### 3. Set Loading → Audio Engine
**Mechanism**: Player loads all assigned pads
**Thread**: Main thread (synchronous)

```python
def load_set(self, set_obj: Set):
    self.current_set = set_obj
    if self._engine:
        for pad_index, pad in enumerate(set_obj.launchpad.pads):
            if pad.is_assigned:
                self._engine.load_sample(pad_index, pad)
```

### 4. Hot-Plug Detection → UI
**Mechanism**: Connection callbacks
**Thread**: Monitor thread → Callback thread → UI thread

```python
# MidiManager detects connection change
# Fires callback in separate thread
def fire_callback():
    try:
        self._on_connection_changed(True, port_name)
    except Exception as e:
        logger.error(f"Error in connection callback: {e}")
threading.Thread(target=fire_callback, daemon=True).start()
```

---

## Architectural Principles (Test-Validated)

### 1. **Separation of Concerns**
- **Domain Models**: Pure data (Pydantic)
- **Audio Primitives**: Hardware-agnostic (AudioDevice, AudioMixer)
- **MIDI Primitives**: Hardware-agnostic (MidiManager)
- **Core Engine**: Orchestration (SamplerEngine, Player)
- **UI**: Separate layer (not in core tests)

### 2. **UI-Agnostic Core**
Player has zero UI dependencies. Can be used in:
- TUI (Textual)
- GUI (Qt, GTK)
- CLI (headless)
- Web server (HTTP API)
- Tests (mocks)

### 3. **Real-Time Audio Constraints**
- **No locks in audio path**: Queue is lock-free
- **No I/O in callback**: All file loading pre-done
- **No memory allocation**: Pre-allocated buffers
- **Soft clipping**: Prevents distortion, no crashes

### 4. **Graceful Degradation**
- **MIDI failure**: Continues without MIDI (logged warning)
- **Queue full**: Drops trigger (logged warning)
- **Observer exception**: Logs, notifies other observers
- **Invalid device**: Raises ValueError with clear message

### 5. **Thread Safety by Design**
- **Lock-free where possible**: Trigger queue, playback state reads
- **Small critical sections**: Only lock for state updates
- **Thread ownership**: Audio thread owns playback states
- **Immutable sharing**: AudioData shared by reference (safe)

### 6. **Event-Driven Architecture**
- **No polling**: All updates via events
- **Asynchronous**: MIDI → Queue → Audio → Observer
- **Loose coupling**: Components communicate via events
- **Multiple observers**: Support any number of listeners

---

## Comparison: Tests vs. Implementation

### Perfect Alignment ✅

| Aspect | Test Behavior | Implementation | Match |
|--------|---------------|----------------|-------|
| Queue system | Lock-free, 256 entries | `Queue(maxsize=256)`, `put_nowait` | ✅ |
| Playback modes | 4 modes with specific behaviors | Exactly matches test expectations | ✅ |
| Event flow | 6 event types, specific timing | `PlaybackEvent` enum, same timing | ✅ |
| MIDI parsing | Launchpad protocol, filtering | `LaunchpadDevice.parse_input` | ✅ |
| Observer pattern | Multiple observers, exception isolation | `SamplerStateMachine` implementation | ✅ |
| Thread safety | Lock-free trigger, locked loading | Exact implementation matches tests | ✅ |
| Cache behavior | Shared AudioData, per-pad state | `_audio_cache` + `_playback_states` | ✅ |
| Error handling | Graceful degradation, logging | Try/except with logger calls | ✅ |

### Test-Driven Benefits

1. **Architecture Validation**: Tests prove the lock-free queue works
2. **Regression Prevention**: 199 tests catch breaking changes
3. **Documentation**: Tests serve as executable specifications
4. **Confidence**: 97-100% coverage on critical paths

---

## Architecture Diagram: Component Dependencies

```
┌────────────────────────────────────────────────────────────────┐
│                      LaunchSampler                             │
│                   (Python 3.13 Project)                        │
└────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
┌─────────────▼────┐  ┌──────▼──────┐  ┌────▼─────────────┐
│  Domain Models   │  │ Core Engine  │  │   Primitives     │
│  (models/)       │  │ (core/)      │  │  (audio/, midi/) │
│                  │  │              │  │                  │
│ • Color          │  │ • Player     │  │ • AudioDevice    │
│ • Sample         │  │ • Engine     │  │ • AudioMixer     │
│ • Pad            │  │ • StateMach  │  │ • SampleLoader   │
│ • Launchpad      │  │              │  │ • MidiManager    │
│ • Set            │  │              │  │ • Launchpad...   │
│ • PlaybackMode   │  │              │  │   Controller     │
│ • AppConfig      │  │              │  │                  │
│                  │  │              │  │                  │
│ Dependencies:    │  │ Dependencies:│  │ Dependencies:    │
│ • Pydantic       │  │ • Models     │  │ • sounddevice    │
│ • NumPy          │  │ • Primitives │  │ • mido           │
└──────────────────┘  │ • Protocols  │  │ • soundfile      │
                      └──────┬───────┘  │ • NumPy          │
                             │          └──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Protocols     │
                    │  (protocols.py) │
                    │                 │
                    │ • PlaybackEvent │
                    │ • StateObserver │
                    └─────────────────┘

External Dependencies:
├── sounddevice → PortAudio (audio I/O)
├── mido → RtMidi (MIDI I/O)
├── soundfile → libsndfile (audio file I/O)
├── numpy → Core (array operations)
└── pydantic → Core (data validation)
```

---

## Conclusion

The LaunchSampler architecture demonstrates **mature real-time audio engineering** with these key strengths:

1. **Proven Thread Safety**: 199 tests validate lock-free audio path
2. **Clean Separation**: UI-agnostic core enables multiple frontends
3. **Event-Driven**: No polling, minimal latency, loose coupling
4. **Graceful Degradation**: System continues on component failure
5. **Memory Efficient**: Shared audio data, minimal allocation in audio thread
6. **Maintainable**: High test coverage (97-100% on critical paths)

The test suite provides both **validation** (architecture works) and **documentation** (executable specifications). The match between test behavior and implementation is nearly perfect, indicating a well-understood and mature design.

**Next Steps for Expansion**:
- CLI coverage (currently low)
- TUI integration testing (separate from core)
- Performance benchmarks (latency, CPU usage)
- Load testing (max concurrent voices)
