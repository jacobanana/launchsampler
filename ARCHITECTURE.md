# LaunchSampler TUI Architecture

**Document Purpose**: Global architecture diagram showing TUI layers and their responsibilities
**Last Updated**: November 16, 2025
**Status**: Current architecture with event-driven editing system

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Composition Tree Diagram](#composition-tree-diagram)
3. [Global Architecture Diagram](#global-architecture-diagram)
4. [Layer Responsibilities](#layer-responsibilities)
5. [Component Details](#component-details)
6. [Event Flow Architecture](#event-flow-architecture)
7. [Threading Model](#threading-model)
8. [Key Design Patterns](#key-design-patterns)

---

## Executive Summary

LaunchSampler is a real-time audio sampling application for Novation Launchpad controllers with a Terminal User Interface (TUI). The architecture follows a **layered, event-driven design** with clear separation of concerns:

**Architecture Characteristics:**
- **Layered Architecture**: 5 distinct layers (Presentation → Services → Core → Infrastructure → Domain)
- **Event-Driven**: Observer pattern for both playback and editing events
- **UI-Agnostic Core**: Player and audio engine have no UI dependencies
- **Thread-Safe**: Proper synchronization across MIDI, audio, and UI threads
- **Lock-Free Audio Path**: Sub-millisecond latency trigger queue
- **Hot-Plug Support**: Automatic MIDI device detection and reconnection

**Test Coverage**: 262 passing tests, 45% overall (97% Player, 94% SamplerEngine, 100% StateMachine, 100% SetManagerService)

---

## Composition Tree Diagram

This diagram shows the "has-a" relationships between components (composition), not the layered architecture:

```
LaunchpadSampler (TUI App)
│
├── launchpad: Launchpad (OWNED - single source of truth)
│   └── Pad[64]
│       └── Sample (optional)
│
├── current_set: Set (metadata wrapper)
│   ├── name: str
│   ├── samples_root: Path
│   ├── launchpad: Launchpad (reference to app's launchpad)
│   ├── created_at: datetime
│   └── modified_at: datetime
│
├── SetManagerService
│   └── config: AppConfig
│
├── EditorService
│   ├── _app: LaunchpadSampler (reference)
│   ├── AppConfig
│   └── _observers: list[EditObserver]
│
├── Player
│   ├── AudioDevice
│   │   └── PortAudio stream
│   │
│   ├── SamplerEngine
│   │   ├── AudioDevice (reference)
│   │   ├── SamplerStateMachine
│   │   │   └── _observers: list[StateObserver]
│   │   ├── AudioMixer
│   │   ├── SampleLoader
│   │   ├── _playback_states: dict[int, PlaybackState]
│   │   │   └── PlaybackState
│   │   │       ├── AudioData (shared reference)
│   │   │       ├── mode: PlaybackMode
│   │   │       ├── volume: float
│   │   │       └── position: float
│   │   ├── _audio_cache: dict[str, AudioData]
│   │   └── _trigger_queue: Queue
│   │
│   ├── LaunchpadController
│   │   ├── MidiManager
│   │   │   ├── MidiInputManager
│   │   │   │   └── mido.Input
│   │   │   ├── MidiOutputManager
│   │   │   │   └── mido.Output
│   │   │   └── _monitor_thread: Thread
│   │   └── LaunchpadDevice (protocol)
│   │
│   └── current_set: Set
│       ├── Launchpad (reference)
│       ├── name: str
│       └── samples_root: Path
│
└── Widgets (Textual framework)
    ├── PadGrid (stateless - data-driven)
    │   └── PadWidget[64] (created via initialize_pads)
    │       ├── pad_index: int
    │       └── pad: Pad (passed on updates)
    │
    ├── PadDetailsPanel
    │   ├── NoTabInput (name)
    │   ├── Input (volume)
    │   ├── Input (move-to)
    │   ├── RadioSet (mode buttons)
    │   └── Button[4] (Browse, Delete, Test, Stop)
    │
    ├── StatusBar
    │   ├── mode: str
    │   ├── audio_device: str
    │   ├── midi_status: str
    │   └── voice_count: int
    │
    └── Screens (pushed to screen stack)
        ├── FileBrowserScreen
        │   ├── DirectoryTree
        │   └── Input (path)
        ├── DirectoryBrowserScreen
        │   ├── DirectoryTree
        │   └── Input (path)
        ├── SetFileBrowserScreen
        │   ├── DirectoryTree
        │   ├── Input (path)
        │   └── Label (metadata preview)
        ├── SaveSetBrowserScreen
        │   ├── DirectoryTree
        │   ├── Input (path)
        │   └── Input (filename)
        ├── MoveConfirmationModal
        ├── ClearConfirmationModal
        └── PasteConfirmationModal

Domain Models (used throughout, not owned):
├── Color (RGB: 0-127)
├── Sample (path, name, metadata)
├── Pad (row, col, sample, mode, color, volume)
├── Launchpad (8x8 grid of Pads)
├── Set (name, launchpad, samples_root)
├── PlaybackMode (ONE_SHOT | LOOP | HOLD | LOOP_TOGGLE)
└── AppConfig (preferences, paths)
```

**Key Observations**:
- **LaunchpadSampler** is the root - composes everything and **owns Launchpad** (single source of truth)
- **SetManagerService**: Stateless I/O service for loading/saving sets
- **EditorService**: References app via property to access current launchpad
- **PadGrid**: Stateless widget - pad data passed explicitly on updates
- **Set model**: Wraps app's launchpad reference + metadata (name, samples_root, timestamps)
- **Shared references**: AudioData cached and shared across pads
- **64 instances**: PadWidget array in PadGrid, Pad array in Launchpad, PlaybackState dict in SamplerEngine
- **Observer lists**: Stored in EditorService and SamplerStateMachine
- **Queue pattern**: Lock-free trigger queue in SamplerEngine
- **Thread ownership**: Monitor thread in MidiManager, audio callback in AudioDevice

---

## Global Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                               │
│                            (src/tui/widgets/)                               │
│                                                                             │
│  ┌────────────────────┐  ┌────────────────┐  ┌──────────────────────────┐ │
│  │   PadGrid (8x8)    │  │ PadDetailsPanel│  │   StatusBar / Modals     │ │
│  │                    │  │                │  │                          │ │
│  │ • Layout container │  │ • Edit controls│  │ • Mode display           │ │
│  │ • 64 PadWidgets    │  │ • Volume/name  │  │ • Device status          │ │
│  │ • Selection vis    │  │ • Mode buttons │  │ • Confirmations          │ │
│  │ • Playing state    │  │ • Browse/test  │  │                          │ │
│  └────────┬───────────┘  └────────┬───────┘  └──────────────────────────┘ │
│           │                       │                                        │
│           └───────────────┬───────┘                                        │
└───────────────────────────┼────────────────────────────────────────────────┘
                            │ Message Passing (Textual framework)
┌───────────────────────────┼────────────────────────────────────────────────┐
│                      APPLICATION COORDINATOR LAYER                         │
│                         (src/tui/app.py - 1,226 lines)                     │
│                                                                             │
│                        LaunchpadSampler (Main App)                         │
│                                                                             │
│  Responsibilities:                                                          │
│  • Textual app lifecycle and UI orchestration                             │
│  • Mode management (Edit/Play switching)                                  │
│  • Widget message handling and routing                                    │
│  • Event observation (EditObserver, MidiObserver, StateObserver)          │
│  • User action bindings (keyboard shortcuts)                              │
│  • Screen stack management (file browsers, modals)                        │
│                                                                             │
│  Implements Protocols:                                                     │
│  • EditObserver: on_edit_event() → Updates UI automatically               │
│  • MidiObserver: on_midi_event() → Shows MIDI input feedback              │
│  • StateObserver: on_playback_event() → Shows playback state              │
│                                                                             │
│  Component References:                                                     │
│  • EditorService (editing operations)                                     │
│  • Player (playback/MIDI coordination)                                    │
│  • Widgets (UI components)                                                │
│  • Screens (modal dialogs)                                                │
└────┬────────────────────────────────────────────────┬───────────────────────┘
     │                                                │
     │ EditEvents ←                                   │ PlaybackEvents ←
     │ MidiEvents ←                                   │
     │                                                │
┌────▼────────────────────┐              ┌───────────▼──────────────────────┐
│    SERVICE LAYER        │              │       CORE LAYER                 │
│   (src/tui/services/)   │              │      (src/core/)                 │
│                         │              │                                  │
│   EditorService         │              │   Player (Orchestrator)          │
│                         │              │                                  │
│ • Pad selection         │              │ • Lifecycle (start/stop)         │
│ • Sample assignment     │◄─────────────┤ • Set loading                    │
│ • Set save/load         │  Observes    │ • MIDI → Audio routing           │
│ • Volume/mode changes   │  EditEvents  │ • Event forwarding               │
│ • Copy/paste/move       │              │ • Query methods                  │
│ • Event publishing      │              │                                  │
│   (EditEvent)           │              │ Implements:                      │
│                         │              │ • EditObserver (audio sync)      │
│ No UI dependencies!     │              │ • StateObserver (event forward)  │
└─────────┬───────────────┘              └──────┬───────────────────────────┘
          │                                     │
          │ Mutates Domain Models               │ Coordinates Components
          │                                     │
          ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                │
│                 (src/audio/, src/midi/, src/devices/)                       │
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐ │
│  │  SamplerEngine       │  │ LaunchpadController  │  │  Screens (TUI)   │ │
│  │                      │  │                      │  │                  │ │
│  │ • Lock-free queue    │  │ • MIDI I/O           │  │ • BaseBrowser    │ │
│  │ • Voice management   │  │ • Hot-plug support   │  │   (Template)     │ │
│  │ • Audio mixing       │  │ • Message parsing    │  │ • FileBrowser    │ │
│  │ • Sample caching     │  │ • LED control        │  │ • DirBrowser     │ │
│  │ • Playback modes     │  │ • Auto-reconnect     │  │ • SetBrowser     │ │
│  │ • Event publishing   │  │ • Event callbacks    │  │                  │ │
│  │   (PlaybackEvent)    │  │   (MidiEvent)        │  │                  │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────────────┘ │
│             │                         │                                    │
│             │                         │                                    │
│  ┌──────────▼───────────┐  ┌──────────▼───────────┐                       │
│  │   AudioDevice        │  │    MidiManager       │                       │
│  │                      │  │                      │                       │
│  │ • Platform API       │  │ • Port monitoring    │                       │
│  │   selection (ASIO,   │  │ • Input/Output mgmt  │                       │
│  │   WASAPI, CoreAudio) │  │ • Device filtering   │                       │
│  │ • Stream management  │  │ • Thread polling     │                       │
│  │ • Audio callback     │  │                      │                       │
│  └──────────┬───────────┘  └──────────────────────┘                       │
│             │                                                              │
│  ┌──────────▼───────────┐  ┌────────────────────────────────────────────┐ │
│  │  AudioMixer          │  │  SampleLoader • AudioData • PlaybackState  │ │
│  │                      │  │                                            │ │
│  │ • Multi-source mix   │  │ • WAV/MP3/FLAC loading                     │ │
│  │ • Channel conversion │  │ • Resampling                               │ │
│  │ • Master volume      │  │ • Zero-copy buffers                        │ │
│  │ • Soft clipping      │  │ • Mode-based playback                      │ │
│  └──────────────────────┘  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Uses
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             DOMAIN LAYER                                    │
│                          (src/models/ - Pydantic)                           │
│                                                                             │
│  Pure Data Models (Immutable, Serializable, Type-Safe):                   │
│                                                                             │
│  • Color: RGB validation (0-127), factory methods                          │
│  • Sample: File path, metadata, existence validation                      │
│  • Pad: Position (row/col), sample, mode, color, volume                   │
│  • Launchpad: 8x8 grid (64 pads), coordinate ↔ MIDI conversion            │
│  • Set: Named configuration, samples_root, serialization                  │
│  • PlaybackMode: ONE_SHOT | LOOP | HOLD | LOOP_TOGGLE                     │
│  • AppConfig: User preferences, default paths                             │
│                                                                             │
│  Zero dependencies on upper layers - Pure business rules                  │
└─────────────────────────────────────────────────────────────────────────────┘

External Dependencies:
├── textual → TUI framework (Presentation layer)
├── sounddevice → PortAudio wrapper (Audio I/O)
├── mido → RtMidi wrapper (MIDI I/O)
├── soundfile → libsndfile wrapper (Audio file I/O)
├── numpy → Array operations (Audio data)
└── pydantic → Data validation (Domain models)
```

---

## Ownership and State Management

### Single Source of Truth: App Owns Launchpad

**Key Architectural Decision**: `LaunchpadSampler` (the TUI app) **owns the Launchpad model** as the single source of truth for runtime state.

**Rationale**:
- **Eliminates reference synchronization**: No need to update multiple components when loading a new set
- **Clear ownership**: Launchpad lifecycle matches app lifecycle
- **Event-driven updates**: Services and widgets react to changes via events, not stale references
- **Simplified Set loading**: Just replace `app.launchpad`, observers handle synchronization

### Component Access Patterns

**EditorService** (Option 1B):
```python
class EditorService:
    def __init__(self, app: "LaunchpadSampler", config: AppConfig):
        self._app = app  # Reference to app

    @property
    def launchpad(self) -> Launchpad:
        return self._app.launchpad  # Always current
```
- Accesses launchpad via property
- Always gets current reference
- Clean API (methods don't need launchpad parameter)

**PadGrid** (Option 2A):
```python
class PadGrid(Container):
    def initialize_pads(self, launchpad: Launchpad):
        # Create widgets from data

    def update_pad(self, pad_index: int, pad: Pad):
        # Pad data passed explicitly
```
- Stateless widget
- Data passed explicitly when needed
- No stored launchpad reference

**SetManagerService** (New):
```python
class SetManagerService:
    def load_from_file(self, path: Path) -> Set:
        # Returns Set, doesn't store it

    def save_to_file(self, set_obj: Set, path: Path):
        # Takes data, doesn't store it
```
- Pure I/O operations
- Stateless service
- Extracted from app.py (lines 163-256)

### Set Loading Flow

**Before** (distributed ownership):
```python
def _load_set(self, new_set: Set):
    self.current_set = new_set
    self.editor.launchpad = new_set.launchpad  # Manual sync
    grid.launchpad = new_set.launchpad          # Manual sync
    for i in range(64):
        grid.update_pad(i, new_set.launchpad.pads[i])  # Manual update
```

**After** (single ownership):
```python
def _load_set(self, loaded_set: Set):
    # Update app's launchpad (single source of truth)
    self.launchpad = loaded_set.launchpad

    # Update Set metadata to reference app's launchpad
    self.current_set = Set(
        name=loaded_set.name,
        launchpad=self.launchpad,  # Reference, not copy
        ...
    )

    # Load into player if running
    if self.player.is_running:
        self.player.load_set(self.current_set)

    # Synchronize UI directly (app-level operation, not an edit event)
    self._sync_ui_with_launchpad()
```

**Benefits**:
- ✅ No manual reference synchronization needed
- ✅ App handles its own UI updates (no layering violation)
- ✅ Impossible to have stale references
- ✅ ~50 lines of manual sync code eliminated
- ✅ No fake "edit events" for non-edit operations

---

## Layer Responsibilities

### Layer 1: Domain Models (Bottom)
**Location**: `src/launchsampler/models/`
**Purpose**: Pure data models with business rules
**Dependencies**: None (zero coupling to upper layers)

**Components**:
- **Pydantic Models**: Color, Sample, Pad, Launchpad, Set, PlaybackMode, AppConfig
- **Responsibilities**:
  - Data validation and type safety
  - Serialization/deserialization (JSON)
  - Business rules (e.g., 64 pads in 8x8 grid)
  - Coordinate transformations (row/col ↔ MIDI note)

**Key Principle**: Immutable value objects - no side effects, no I/O, no state management

---

### Layer 2: Infrastructure Layer
**Location**: `src/launchsampler/audio/`, `src/launchsampler/midi/`, `src/launchsampler/devices/`
**Purpose**: Hardware abstraction and low-level operations
**Dependencies**: Domain models, external libraries (sounddevice, mido)

**Components**:

#### Audio Subsystem
- **AudioDevice**: Platform-specific audio I/O (ASIO, WASAPI, CoreAudio)
- **AudioMixer**: Multi-source audio mixing with soft clipping
- **SampleLoader**: Audio file loading with format detection and resampling
- **AudioData**: Immutable audio buffer (dataclass with NumPy arrays)
- **PlaybackState**: Per-pad runtime state (position, playing, volume)

#### MIDI Subsystem
- **MidiManager**: Generic MIDI I/O with hot-plug detection
- **LaunchpadController**: Launchpad-specific protocol (message parsing, LED control)
- **LaunchpadDevice**: Device matching and message formatting

#### Audio Engine
- **SamplerEngine** (179 lines, 94% coverage):
  - Lock-free 256-entry trigger queue (sub-millisecond latency)
  - Voice management and playback state tracking
  - Audio mixing via AudioMixer composition
  - Sample caching (shared AudioData across pads)
  - State machine integration for event dispatch
  - Supports 4 playback modes (ONE_SHOT, LOOP, HOLD, LOOP_TOGGLE)

**Key Principle**: Hardware-agnostic abstractions with proper threading and error handling

---

### Layer 3: Core Layer
**Location**: `src/launchsampler/core/`
**Purpose**: Application orchestration without UI dependencies
**Dependencies**: Infrastructure layer, domain models, protocols

**Components**:

#### Player (154 lines, 97% coverage)
**Role**: UI-agnostic playback coordinator

**Responsibilities**:
- Lifecycle management (start/stop components)
- Set loading into audio engine
- MIDI event → Audio trigger routing
- Event observation and forwarding
- Query methods for status and state

**Implements Protocols**:
- **StateObserver**: Receives playback events from SamplerEngine
- **EditObserver**: Receives editing events from EditorService, syncs audio engine

**Key Methods**:
```python
# Lifecycle
start(initial_set=None) → bool
stop() → None

# Set Management
load_set(set_obj: Set) → None

# Playback Control
trigger_pad(pad_index: int) → None
release_pad(pad_index: int) → None
stop_pad(pad_index: int) → None
stop_all() → None

# Query
is_running: bool
is_midi_connected: bool
active_voices: int
is_pad_playing(pad_index: int) → bool
```

**Key Principle**: Reusable across TUI, GUI, CLI, web interfaces - zero UI coupling

---

### Layer 4: Service Layer
**Location**: `src/launchsampler/tui/services/`
**Purpose**: Business logic for editing operations
**Dependencies**: Domain models, protocols

**Components**:

#### EditorService (678 lines)
**Role**: UI-agnostic pad editing and set management

**Responsibilities**:
- Pad selection state management
- Sample assignment and clearing
- Pad property changes (mode, volume, name)
- Set save/load operations
- Copy/paste/move/duplicate operations
- **Event publishing** (EditEvent) for automatic synchronization

**State**:
- `launchpad: Launchpad` - The model being edited
- `config: AppConfig` - Application configuration
- `selected_pad_index: Optional[int]` - Current selection
- `_clipboard: Optional[Pad]` - Copy/paste buffer
- `_observers: list[EditObserver]` - Event subscribers

**Event System** (Observer Pattern):
- **EditEvent types**: PAD_ASSIGNED, PAD_CLEARED, PAD_MOVED, PAD_DUPLICATED, PAD_MODE_CHANGED, PAD_VOLUME_CHANGED, PAD_NAME_CHANGED, PADS_CLEARED, SET_LOADED
- **Flow**: Service operation → `_notify_observers()` → All registered observers
- **Observers**: Player (audio sync), App (UI sync)

**Key Operations**:
```python
# Selection
select_pad(index: int) → Pad
get_pad(index: int) → Pad

# Sample Management
assign_sample(index: int, path: Path) → Pad
clear_pad(index: int) → Pad

# Properties
set_pad_mode(index: int, mode: PlaybackMode) → Pad
set_pad_volume(index: int, volume: float) → Pad
set_sample_name(index: int, name: str) → Pad

# Set Operations
save_set(path: Path) → None
load_set(path: Path) → Set

# Clipboard
copy_pad(index: int) → Pad
paste_pad(index: int, overwrite: bool) → Pad
cut_pad(index: int) → Pad

# Advanced
move_pad(source: int, target: int, swap: bool) → tuple[Pad, Pad]
duplicate_pad(source: int, target: int) → Pad
```

**Key Principle**: Service layer pattern - pure business logic, no UI/audio dependencies

---

### Layer 5: Presentation Layer
**Location**: `src/launchsampler/tui/widgets/`, `src/launchsampler/tui/screens/`
**Purpose**: User interface components (Textual framework)
**Dependencies**: All lower layers

**Components**:

#### Widgets (Reusable UI Components)

**PadWidget**:
- Single pad display (presentation only)
- Shows index, sample name, visual state
- CSS classes for modes (one_shot, loop, hold, loop_toggle)
- States: selected, midi_on, active (playing)
- Posts `Selected` message on click

**PadGrid**:
- 8x8 layout container for 64 PadWidgets
- Matches physical Launchpad layout
- Manages selection visualization
- Forwards selection events to parent
- Methods: `update_pad()`, `select_pad()`, `set_pad_playing()`, `set_pad_midi_on()`

**PadDetailsPanel** (474 lines):
- Comprehensive edit interface for selected pad
- Displays: index, location, sample info, audio metadata
- Controls: name input, volume slider, move-to-index
- Mode radio buttons (One-Shot, Hold, Loop, Loop Toggle)
- Action buttons: Browse, Delete, Test, Stop
- Posts: `VolumeChanged`, `NameChanged`, `MovePadRequested`
- Mode-aware: Disables controls in play mode

**StatusBar**:
- Current mode (Edit/Play) with visual styling
- Audio device name
- MIDI device connection status
- Active voice count

**Confirmation Modals**:
- MoveConfirmationModal: Swap vs Overwrite choice
- ClearConfirmationModal: Delete confirmation
- PasteConfirmationModal: Overwrite confirmation

#### Screens (Modal Dialogs)

**BaseBrowserScreen** (433 lines):
- Abstract template for file/directory browsing
- Template Method pattern with hooks
- Features: filtered tree, path input, keyboard navigation
- Abstract methods: `_is_valid_selection()`, `_get_selection_value()`, `_get_title()`

**Concrete Browsers**:
- **FileBrowserScreen**: Audio file selection (.wav, .mp3, .flac, .ogg, .aiff)
- **DirectoryBrowserScreen**: Directory selection for bulk loading
- **SetFileBrowserScreen**: Saved set file (.json) with metadata preview
- **SaveSetBrowserScreen**: Save location with filename input

---

### Layer 6: Application Coordinator
**Location**: `src/launchsampler/tui/app.py` (1,226 lines)
**Purpose**: Textual app coordination - orchestrates UI, services, and mode management
**Dependencies**: All layers

#### LaunchpadSampler (Main App)
**Role**: TUI application coordinator

**Implements Protocols** (duck typing):
- **EditObserver**: `on_edit_event()` → Updates UI automatically
- **MidiObserver**: `on_midi_event()` → Shows MIDI input (green borders)
- **StateObserver**: `on_playback_event()` → Shows playback state (yellow backgrounds)

**Architecture Sections** (documented in source):
1. **Initialization & Lifecycle** (lines 85-161)
2. **Set Management** (lines 162-256)
3. **Mode Management** (lines 257-320)
4. **Observer Protocol Implementations** (lines 321-401)
5. **Widget Message Handlers** (lines 402-522)
6. **UI Update Helpers** (lines 523-629)
7. **User Actions - File Operations** (lines 630-763)
8. **User Actions - Pad Editing** (lines 764-877)
9. **User Actions - Pad Operations** (lines 878-969)
10. **User Actions - Playback** (lines 970-1023)
11. **Operation Helpers** (lines 1024-1226)

**Key State**:
- `config: AppConfig` - Configuration
- `current_set: Set` - Active set with launchpad
- `set_name: str` - Current set name
- `_sampler_mode: str` - UI mode ("edit" or "play")
- `player: Player` - Audio/MIDI manager
- `editor: EditorService` - Edit operations

**Key Responsibilities**:
- Textual app lifecycle (on_mount, compose)
- Mode switching (edit ↔ play)
- Widget message routing
- Event observation (automatic UI sync)
- Action bindings (keyboard shortcuts)
- Screen stack management (modals)

**Key Principle**: Thin UI layer - delegates to services, uses event-driven updates

---

## Component Details

### PadGrid Component Hierarchy

```
PadGrid (Container)
├── PadWidget (0,0)  ─┐
├── PadWidget (0,1)   │
├── ...               │ 64 instances
├── PadWidget (7,6)   │
└── PadWidget (7,7)  ─┘

Message Flow:
PadWidget.on_click()
  → Posts PadWidget.Selected
  → PadGrid.on_pad_widget_selected()
  → Posts PadGrid.PadSelected
  → App.on_pad_grid_pad_selected()
```

### Screen Modal Stack

```
Main Screen (LaunchpadSampler)
├── Pushed: FileBrowserScreen
│   └── Callback: handle_file(path)
├── Pushed: DirectoryBrowserScreen
│   └── Callback: handle_directory(path)
├── Pushed: SetFileBrowserScreen
│   └── Callback: handle_set_file(path)
├── Pushed: SaveSetBrowserScreen
│   └── Callback: handle_save_path(path, name)
└── Pushed: Confirmation Modals
    └── Callback: handle_choice(result)

Pattern: push_screen(screen, callback) → async modal
```

---

## Event Flow Architecture

### Event Types and Protocols

```python
# Playback Events (Audio Thread → UI Thread)
class PlaybackEvent(Enum):
    NOTE_ON = "note_on"              # MIDI input (always)
    NOTE_OFF = "note_off"            # MIDI release (always)
    PAD_TRIGGERED = "pad_triggered"  # Audio trigger queued
    PAD_PLAYING = "pad_playing"      # Audio started
    PAD_STOPPED = "pad_stopped"      # Audio stopped by user
    PAD_FINISHED = "pad_finished"    # Audio completed naturally

@runtime_checkable
class StateObserver(Protocol):
    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None: ...

# Editing Events (UI Thread → UI/Audio Threads)
class EditEvent(Enum):
    PAD_ASSIGNED = "pad_assigned"
    PAD_CLEARED = "pad_cleared"
    PAD_MOVED = "pad_moved"
    PAD_DUPLICATED = "pad_duplicated"
    PAD_MODE_CHANGED = "pad_mode_changed"
    PAD_VOLUME_CHANGED = "pad_volume_changed"
    PAD_NAME_CHANGED = "pad_name_changed"
    PADS_CLEARED = "pads_cleared"
    SET_LOADED = "set_loaded"

@runtime_checkable
class EditObserver(Protocol):
    def on_edit_event(
        self,
        event: EditEvent,
        pad_indices: list[int],
        pads: list[Pad]
    ) -> None: ...

# MIDI Events (MIDI Thread → UI Thread)
class MidiEvent(Enum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"

@runtime_checkable
class MidiObserver(Protocol):
    def on_midi_event(self, event: MidiEvent, pad_index: int) -> None: ...
```

### User Action → Sample Assignment Flow

```
User presses 'b' (browse)
  │
  ▼
App.action_browse_sample()
  │
  ├─ Validate: selected pad exists?
  │
  └─ Push FileBrowserScreen with callback
       │
       ▼
     User selects file
       │
       ▼
     Callback: handle_file(file_path)
       │
       ▼
     EditorService.assign_sample(index, path)
       │
       ├─ Validate file exists
       ├─ Create Sample from file
       ├─ Update Pad model (sample, volume, mode)
       │
       └─ Fire EditEvent.PAD_ASSIGNED
            │
            ├──────────────────────┬─────────────────────┐
            │                      │                     │
            ▼                      ▼                     ▼
       Player (EditObserver)  App (EditObserver)   Future Observers
            │                      │
            │                      │
       engine.load_sample()   _update_pad_ui()
            │                      │
            │                      ├─ Update PadGrid
            │                      └─ Update PadDetailsPanel
            │
       Audio engine loaded
```

**Key Benefits**:
- ✅ **Automatic synchronization**: No manual `_reload_pad()` or `_refresh_pad_ui()`
- ✅ **Decoupled**: EditorService doesn't know about Player or App
- ✅ **Extensible**: New observers can be added without modifying existing code
- ✅ **Testable**: EditorService can be tested in isolation

### MIDI Input → Audio Playback Flow (Play Mode)

```
User presses Launchpad pad
  │
  ▼
LaunchpadController (MIDI Thread)
  │
  ├─ Parse MIDI message: ("pad_press", note)
  │
  └─ Call: _on_pad_pressed(note)
       │
       ▼
     Player._on_pad_pressed(index)
       │
       ├─ Fire MidiEvent.NOTE_ON → App (green border)
       │
       └─ If pad.is_assigned: trigger_pad(index)
            │
            ▼
          SamplerEngine.trigger_pad(index)
            │
            ├─ Queue.put_nowait(("trigger", index))  [Lock-free!]
            │
            └─ Audio callback processes queue
                 │
                 ├─ state.start()
                 ├─ Fire PlaybackEvent.PAD_TRIGGERED
                 ├─ Fire PlaybackEvent.PAD_PLAYING
                 │
                 └─ Forward to App → Yellow background
```

### Mode Switching Flow

```
User presses 'e' (edit mode) or 'p' (play mode)
  │
  ▼
App.action_switch_mode(mode)
  │
  └─ _set_mode(mode)
       │
       ├─ Update _sampler_mode
       ├─ Set subtitle ("EDIT MODE" / "PLAY MODE")
       │
       ├─ If edit mode:
       │    ├─ Show PadDetailsPanel
       │    └─ Restore grid selection
       │
       ├─ If play mode:
       │    ├─ Hide PadDetailsPanel
       │    └─ Clear grid selection
       │
       └─ Update StatusBar

Note: Player keeps running - audio/MIDI continue in both modes
```

---

## Threading Model

### Thread Responsibilities

| Thread | Owned By | Operations | Critical Sections |
|--------|----------|------------|-------------------|
| **Main/UI** | Textual | Widget updates, user input, app lifecycle | EditorService._event_lock |
| **MIDI Input** | mido | MIDI message reception, callback execution | None (lock-free triggers) |
| **Audio Callback** | PortAudio | Queue processing, mixing, event firing | SamplerEngine._lock (sample loading only) |
| **MIDI Monitor** | LaunchpadController | Device polling (5s interval), auto-reconnect | MidiManager._port_lock |

### Thread Safety Mechanisms

**Lock-Free Operations**:
- Trigger queue: `Queue.put_nowait()` / `Queue.get_nowait()` (256 entries)
- Playback state reads: Audio thread owns, no lock needed
- AudioData sharing: Immutable, safe to share by reference

**Protected Operations**:
- Sample loading: `SamplerEngine._lock`
- Observer list modifications: `EditorService._event_lock`, `SamplerStateMachine._lock`
- MIDI port access: `MidiManager._port_lock`

**Thread Marshaling**:
- MIDI → UI: `app.call_from_thread()` in MidiObserver
- Audio → UI: `app.call_from_thread()` in StateObserver
- UI → Audio: Lock-free queue writes

---

## Key Design Patterns

### 1. Observer Pattern (Event-Driven)
**Used For**: Playback events, editing events, MIDI events
**Benefits**: Loose coupling, multiple observers, automatic synchronization

**Implementation**:
```python
# Subject
class EditorService:
    def _notify_observers(self, event, pad_indices, pads):
        for observer in self._observers:
            observer.on_edit_event(event, pad_indices, pads)

# Observers
class Player(EditObserver):
    def on_edit_event(self, event, pad_indices, pads):
        # Sync audio engine

class LaunchpadSampler(EditObserver):
    def on_edit_event(self, event, pad_indices, pads):
        # Update UI
```

### 2. Service Layer Pattern
**Used For**: EditorService
**Benefits**: UI-agnostic business logic, reusability, testability

**Characteristics**:
- Pure business logic
- No dependencies on UI or audio
- Event publishing for state changes
- Stateful (selection, clipboard)

### 3. Template Method Pattern
**Used For**: BaseBrowserScreen
**Benefits**: Code reuse, consistent behavior, customization points

**Implementation**:
```python
class BaseBrowserScreen(ModalScreen):
    # Template method
    def on_tree_file_selected(self):
        if self._is_valid_selection(path):  # Hook
            value = self._get_selection_value()  # Hook
            self.dismiss(value)

    # Abstract hooks
    @abstractmethod
    def _is_valid_selection(self, path: Path) -> bool: ...

    @abstractmethod
    def _get_selection_value(self) -> Any: ...
```

### 4. Composite Pattern
**Used For**: PadGrid aggregating PadWidgets
**Benefits**: Uniform interface, hierarchical structure

### 5. Decorator Pattern
**Used For**: Mode restriction (`@edit_only`, `@play_only`)
**Benefits**: Declarative, reusable, clear intent

```python
@edit_only
def action_browse_sample(self) -> None:
    # Only callable in edit mode
    ...
```

### 6. Message Passing (Textual Framework)
**Used For**: Widget communication
**Benefits**: Decoupled communication, event bubbling

```python
class PadWidget(Widget):
    def on_click(self):
        self.post_message(self.Selected(self.pad_index))

class PadGrid(Widget):
    def on_pad_widget_selected(self, message: PadWidget.Selected):
        self.post_message(self.PadSelected(message.pad_index))
```

---

## Summary

The LaunchSampler TUI architecture demonstrates **excellent separation of concerns** with a clean layered design:

**Strengths**:
- ✅ Clear layer boundaries (Domain → Infrastructure → Core → Service → Presentation → Coordinator)
- ✅ Event-driven editing system eliminates manual synchronization
- ✅ UI-agnostic core enables multiple frontends
- ✅ Lock-free audio path for minimal latency
- ✅ Thread-safe event propagation across threads
- ✅ Reusable components (widgets, screens, services)
- ✅ High test coverage on critical paths (97-100%)

**Architecture Grade: A-**

The architecture is production-ready with proven patterns. The event-driven editing system (based on EDITING_EVENTS_ARCHITECTURE.md analysis) successfully eliminated ~20 manual synchronization points, making the codebase more maintainable and less error-prone.

**For More Details**:
- Test-based architecture analysis: See [ARCHI_ANALYSIS.md](ARCHI_ANALYSIS.md)
- Editing events implementation: See [EDITING_EVENTS_ARCHITECTURE.md](EDITING_EVENTS_ARCHITECTURE.md)
- Original architecture review: See [TUI_ARCHITECTURE_REVIEW.md](TUI_ARCHITECTURE_REVIEW.md)
