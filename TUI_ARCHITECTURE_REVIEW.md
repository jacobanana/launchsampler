# LaunchSampler TUI Architecture Review

**Date:** November 14, 2025  
**Reviewer:** AI Architecture Analyst

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                TUI LAYER                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      LaunchpadSampler (app.py)                         │ │
│  │  • Main application coordinator                                        │ │
│  │  • Mode switching (Edit/Play)                                          │ │
│  │  • UI event orchestration                                              │ │
│  │  • Lifecycle management                                                │ │
│  └───────┬─────────────────────────────────────────────────┬──────────────┘ │
│          │                                                 │                 │
│          │                                                 │                 │
│  ┌───────▼────────────┐                          ┌─────────▼──────────────┐ │
│  │  EditorService     │                          │   SamplerService       │ │
│  │  • Pad selection   │                          │   • Mode management    │ │
│  │  • Sample assign   │                          │   • Audio/MIDI control │ │
│  │  • Set save/load   │                          │   • Hot-swap modes     │ │
│  │  • Volume/mode set │                          │   • Event routing      │ │
│  └────────────────────┘                          └────────┬───────────────┘ │
│                                                            │                 │
└────────────────────────────────────────────────────────────┼─────────────────┘
                                                             │
┌────────────────────────────────────────────────────────────┼─────────────────┐
│                              CORE LAYER                    │                 │
│                                                   ┌────────▼──────────────┐ │
│                                                   │ SamplerApplication    │ │
│                                                   │ • Facade/Coordinator  │ │
│                                                   │ • Component lifecycle │ │
│                                                   │ • Set management      │ │
│                                                   └───┬──────────┬────────┘ │
│                                                       │          │           │
│                                    ┌──────────────────┘          └─────────┐ │
│                                    │                                       │ │
│                          ┌─────────▼──────────┐              ┌────────────▼──┐
│                          │  SamplerEngine     │              │ Launchpad     │
│                          │  • Audio playback  │              │  Controller   │
│                          │  • Multi-pad mixer │              │ • MIDI I/O    │
│                          │  • Lock-free queue │              │ • Device scan │
│                          │  • Playback states │              │ • Event loop  │
│                          └───┬──────────┬─────┘              └───────┬───────┘
│                              │          │                            │        │
└──────────────────────────────┼──────────┼────────────────────────────┼────────┘
                               │          │                            │
┌──────────────────────────────┼──────────┼────────────────────────────┼────────┐
│                       INFRASTRUCTURE LAYER                           │        │
│                               │          │                            │        │
│                   ┌───────────▼───┐  ┌──▼─────────┐        ┌─────────▼──────┐ │
│                   │  AudioDevice  │  │ AudioMixer │        │  MidiManager   │ │
│                   │  • PortAudio  │  │ • Mix N    │        │  • I/O split   │ │
│                   │  • Callback   │  │   sources  │        │  • Hot-plug    │ │
│                   │  • Buffer mgmt│  │ • Clip/vol │        │  • Device poll │ │
│                   └───────────────┘  └────────────┘        └────────────────┘ │
│                                                                                │
│                   ┌──────────────────────────────────────────────────────────┐│
│                   │  SampleLoader • AudioData • PlaybackState (dataclasses) ││
│                   │  • WAV/MP3/FLAC loading • Zero-copy buffers             ││
│                   └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN MODELS                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  Pydantic Models (Serializable, Type-Safe)                             │ │
│  │  • Set: Configuration + metadata                                       │ │
│  │  • Launchpad: 8x8 grid model                                           │ │
│  │  • Pad: Position + Sample + Mode + Color + Volume                      │ │
│  │  • Sample: Path + metadata                                             │ │
│  │  • AppConfig: User preferences + paths                                 │ │
│  │  • PlaybackMode: ONE_SHOT | LOOP | HOLD                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Roles & Responsibilities

### **TUI Layer**

#### **LaunchpadSampler (app.py)** - Application Coordinator
**Current Role:**
- Main entry point and UI event router
- Orchestrates EditorService and SamplerService
- Manages mode switching (Edit vs Play)
- Handles all keyboard bindings and UI actions
- Updates UI widgets based on state changes
- Tracks UI-specific state (`_playing_pads` set)

**Grade:** B+  
**Assessment:** Well-structured coordinator but has some responsibility creep. Manages too much UI synchronization logic directly.

**Issues:**
1. **Direct UI manipulation scattered** - Multiple `_sync_pad_ui`, `_refresh_pad_ui` calls
2. **UI state tracking** - `_playing_pads` set duplicates what SamplerEngine already knows
3. **Complex event handling** - Many `on_*` methods that could be simplified
4. **Modal management** - Screen stack checks (`len(self.screen_stack) > 1`) scattered throughout

**Proposed Role:** Should focus purely on:
- Routing user input to services
- Displaying service responses in UI
- Mode switching orchestration
- Delegate UI updates to widgets themselves

---

#### **EditorService** - Edit Operations Manager
**Current Role:**
- Manages pad selection state
- Pad editing operations (assign, clear, set mode/volume/name)
- Set save/load operations
- Stateful (tracks `selected_pad_index`)

**Grade:** A-  
**Assessment:** Clean, focused service with minimal responsibilities. UI-agnostic domain logic.

**Strengths:**
- Pure business logic, no UI dependencies
- Clear single responsibility
- Good error handling with exceptions
- Stateless except for selection (reasonable)

**Minor Issues:**
1. **Coupled to Launchpad model** - Could be more generic
2. **Save/load mixed with editing** - Could be split into separate `SetRepository`

**Proposed Role:** Keep as-is, or split into:
- `PadEditor`: Pad manipulation operations
- `SetRepository`: Save/load operations

---

#### **SamplerService** - Audio/MIDI Lifecycle Manager
**Current Role:**
- Wraps `SamplerApplication` with mode-aware API
- Manages edit/play mode transitions
- Hot-swaps MIDI on/off while keeping audio running
- Triggers pad playback
- Routes MIDI events to UI callback
- Wraps internal `SamplerApplication` state

**Grade:** B  
**Assessment:** Good abstraction but awkward wrapping pattern creates confusion.

**Issues:**
1. **Double coordination** - Both `SamplerService` AND `SamplerApplication` coordinate same components
2. **Unclear ownership** - Who owns `SamplerEngine`? Service or Application?
3. **Mode duplication** - `_mode` field redundant with `SamplerApplication._is_running`
4. **Manual component wiring** - Duplicates `SamplerApplication`'s initialization logic

**Proposed Role:** Should be eliminated or radically simplified:
- **Option A:** Remove `SamplerService`, use `SamplerApplication` directly with mode flag
- **Option B:** Make `SamplerService` a true facade that doesn't duplicate internal logic

---

### **Core Layer**

#### **SamplerApplication** - Application Facade
**Current Role:**
- High-level facade for core sampler functionality
- Coordinates `SamplerEngine` + `LaunchpadController`
- Lifecycle management (start/stop)
- Set loading and sample directory scanning
- Event handling (`_handle_pad_pressed/released`)

**Grade:** B-  
**Assessment:** Well-intentioned facade but creates redundancy with `SamplerService`.

**Issues:**
1. **Redundant with SamplerService** - Two coordinators doing similar jobs
2. **Unclear target user** - Is this for TUI or CLI? Both?
3. **Not actually used by CLI** - CLI bypasses this and uses components directly
4. **Stateful lifecycle** - `_is_running` flag adds complexity

**Proposed Role:**
- **Option A:** Keep as high-level API for CLI/scripts, remove from TUI path
- **Option B:** Merge with `SamplerService` as single coordinator
- **Option C:** Convert to pure factory/builder pattern (no state)

---

#### **SamplerEngine** - Audio Playback Engine
**Current Role:**
- Device-agnostic audio playback for N pads
- Sample loading/caching (`_audio_cache`)
- Playback state management per pad (`_playback_states`)
- Lock-free trigger queue for low latency
- Mixing via `AudioMixer` composition
- Audio callback orchestration

**Grade:** A  
**Assessment:** Excellent separation of concerns. Well-designed for performance and concurrency.

**Strengths:**
1. **Device-agnostic** - Works with any MIDI controller
2. **Lock-free triggering** - Queue-based for minimal latency
3. **Proper composition** - Uses `AudioDevice`, `AudioMixer`, `SampleLoader`
4. **Thread-safe** - Careful lock management
5. **Caching** - Smart audio data reuse

**Minor Issue:**
- Could expose `is_pad_playing` more directly instead of through `get_playback_info`

**Proposed Role:** Keep exactly as-is. This is the star component.

---

#### **LaunchpadController** - MIDI Device Manager
**Current Role:**
- High-level Launchpad-specific controller
- Wraps generic `MidiManager` with Launchpad protocol
- Event callbacks for pad press/release
- LED control (not used in TUI?)

**Grade:** A-  
**Assessment:** Clean abstraction with proper device-specific logic separation.

**Strengths:**
1. **Device protocol encapsulation** - `LaunchpadDevice` handles message format
2. **Generic foundation** - Built on `MidiManager`
3. **Simple API** - Clean callback registration

**Unused Feature:**
- `set_pad_color()` never called - LED feedback not implemented

**Proposed Role:** Keep as-is. Consider implementing LED feedback for better UX.

---

### **Infrastructure Layer**

#### **MidiManager** - Generic MIDI I/O Manager
**Current Role:**
- Combines `MidiInputManager` + `MidiOutputManager`
- Device hot-plug support
- Polling for device changes
- Device filtering and port selection

**Grade:** A  
**Assessment:** Excellent generic abstraction. Reusable beyond Launchpad.

**Strengths:**
1. **Separation of concerns** - Split I/O managers
2. **Hot-plug support** - Robust device detection
3. **Configurable** - Device filter + port selector callbacks
4. **Generic** - Not Launchpad-specific

---

#### **AudioDevice** - Audio I/O Abstraction
**Current Role:**
- PortAudio wrapper
- Audio stream management
- Buffer configuration
- Callback registration

**Grade:** A  
**Assessment:** Clean low-level abstraction. Not examined in detail but appears solid.

---

#### **AudioMixer** - Multi-Source Mixer
**Current Role:**
- Mix N playback states into single buffer
- Channel conversion (mono↔stereo)
- Master volume application
- Soft clipping to prevent distortion

**Grade:** A  
**Assessment:** Pure, stateless function object. Perfect design for real-time audio.

**Strengths:**
1. **Stateless** - Just transforms data
2. **Pure functions** - Easy to test
3. **Performance-conscious** - In-place operations
4. **Channel handling** - Proper mono/stereo conversion

---

### **Domain Models**

#### **Pydantic Models (Set, Launchpad, Pad, Sample, etc.)**
**Current Role:**
- Type-safe data models
- Serialization/deserialization
- Validation
- Business rules (e.g., Launchpad has 64 pads)

**Grade:** A  
**Assessment:** Proper use of Pydantic for domain modeling.

**Strengths:**
1. **Immutable-ish** - Models are value objects
2. **Validation** - Type safety + custom validators
3. **Serialization** - JSON save/load built-in
4. **Separation** - No mixing with runtime state

---

#### **Dataclasses (AudioData, PlaybackState)**
**Current Role:**
- Performance-critical runtime state
- Non-serializable data (NumPy arrays)
- Mutable state for audio engine

**Grade:** A  
**Assessment:** Correct choice of dataclass over Pydantic for performance.

**Strengths:**
1. **Performance** - Minimal overhead
2. **Slots** - Memory efficient
3. **Mutable** - Necessary for audio callback
4. **Separated** - Not mixed with domain models

---

## Architecture Patterns Identified

### **✅ Used Well**

1. **Composition over Inheritance**
   - `SamplerEngine` composes `AudioDevice`, `AudioMixer`, `SampleLoader`
   - `LaunchpadController` composes `MidiManager`
   - Clean dependency injection throughout

2. **Service Layer Pattern**
   - `EditorService` and `SamplerService` encapsulate business logic
   - UI-agnostic operations

3. **Facade Pattern**
   - `SamplerApplication` attempts to provide simple API
   - (Though redundant with `SamplerService`)

4. **Observer/Callback Pattern**
   - MIDI events via callbacks
   - UI updates via callbacks (`on_pad_event`)

5. **Repository Pattern (partial)**
   - `Set.load_from_file()` / `save_to_file()`
   - Could be more explicit

6. **Strategy Pattern (implicit)**
   - `PlaybackMode` enum drives different behaviors
   - `PlaybackState` handles mode-specific logic

---

### **⚠️ Anti-Patterns / Issues**

1. **God Object Tendency**
   - `LaunchpadSampler` app does too much UI coordination
   - 600+ lines with too many responsibilities

2. **Duplicate Coordinators**
   - `SamplerService` wraps `SamplerApplication`
   - Both coordinate the same components
   - Unclear which is the "real" coordinator

3. **UI State Duplication**
   - `_playing_pads` set in app duplicates `SamplerEngine` state
   - Should query engine instead of tracking separately

4. **Tight Coupling in TUI Layer**
   - App directly manipulates widget methods (`grid.set_pad_playing()`)
   - Should use message passing or reactive model

5. **Mixed Abstraction Levels**
   - `SamplerService` knows about `_audio_device` and `_engine` internals
   - Violates encapsulation of `SamplerApplication`

---

## Separation of Concerns Analysis

### **Well Separated:**

| Concern | Component | Grade |
|---------|-----------|-------|
| Audio playback | `SamplerEngine` | A |
| MIDI I/O | `MidiManager`, `LaunchpadController` | A |
| Domain models | Pydantic models | A |
| Audio mixing | `AudioMixer` | A |
| Sample loading | `SampleLoader` | A |
| Pad editing | `EditorService` | A- |

### **Poorly Separated:**

| Issue | Components | Problem |
|-------|-----------|---------|
| Coordination logic | `SamplerService` + `SamplerApplication` | Duplicate responsibilities |
| UI synchronization | `LaunchpadSampler` | Scattered `_sync_pad_ui` calls |
| Playback state | `LaunchpadSampler._playing_pads` + `SamplerEngine` | Duplicate tracking |
| Mode management | `SamplerService._mode` + `SamplerApplication._is_running` | Redundant state |

---

## Code Duplication Risks

### **Actual Duplication:**

1. **Component Initialization**
   - `SamplerService.start_play_mode()` duplicates `SamplerApplication.start()`
   - Both create `AudioDevice`, `SamplerEngine`, `LaunchpadController`
   - Both wire up the same event handlers

2. **Sample Loading**
   - `SamplerApplication._handle_pad_pressed()` checks `pad.is_assigned`
   - `SamplerEngine.trigger_pad()` could do this check
   - Logic repeated in multiple places

3. **Pad UI Updates**
   - Multiple methods (`_sync_pad_ui`, `_refresh_pad_ui`, `_update_playback_states`)
   - Do similar things with slight variations
   - Should be consolidated

---

## Data Flow & Ownership Issues

### **Ownership Ambiguity:**

```
Who owns Launchpad model?
├─ LaunchpadSampler.current_set.launchpad
├─ EditorService.launchpad (reference)
└─ SamplerService.launchpad (reference)

Problem: Multiple references, mutation from multiple places
Solution: Single source of truth with change notifications
```

### **State Synchronization:**

```
Playing Pads State:
├─ LaunchpadSampler._playing_pads (UI tracking)
├─ SamplerEngine._playback_states (actual state)
└─ PadGrid.set_pad_playing() (visual state)

Problem: Three places tracking same information
Solution: Query engine directly, remove duplicate tracking
```

---

## Recommendations

### **High Priority (Architectural Issues)**

1. **Eliminate `SamplerService` / `SamplerApplication` redundancy**
   - **Option A:** Merge into single `SamplerCore` class
   - **Option B:** Remove `SamplerService`, use `SamplerApplication` directly
   - **Option C:** Keep `SamplerService` as thin wrapper, remove `SamplerApplication`

2. **Implement proper UI state management**
   - Use reactive model (e.g., signals/events) instead of direct widget calls
   - Widgets should query services for state, not be pushed to
   - Remove `_playing_pads` tracking, query engine directly

3. **Consolidate UI update methods**
   - Single `update_pad_display(pad_index)` method
   - Queries all services and updates all relevant widgets
   - Remove scattered `_sync_pad_ui`, `_refresh_pad_ui`, etc.

### **Medium Priority (Code Quality)**

4. **Split `LaunchpadSampler` app**
   - Extract action handlers into separate `ActionController`
   - Extract UI coordination into `UICoordinator`
   - Leave only Textual-specific setup in `LaunchpadSampler`

5. **Implement LED feedback**
   - Use `LaunchpadController.set_pad_color()` 
   - Show playing pads on hardware
   - Provide visual mode indicators

6. **Extract `SetRepository` from `EditorService`**
   - Separate save/load from editing operations
   - Cleaner separation of concerns
   - Easier to test persistence separately

### **Low Priority (Nice to Have)**

7. **Consider Command pattern for undoable actions**
   - Wrap pad edits in Command objects
   - Enable undo/redo functionality
   - Better action history

8. **Add mediator pattern for widget communication**
   - Reduce direct widget-to-widget coupling
   - Centralize event routing
   - Easier to add new widgets

---

## Overall Grade: **B+**

### **Strengths:**
- ✅ Excellent core audio engine design (`SamplerEngine`)
- ✅ Clean infrastructure abstractions (MIDI, Audio)
- ✅ Good domain modeling with Pydantic
- ✅ Proper composition patterns
- ✅ Thread-safe, performance-conscious code

### **Weaknesses:**
- ⚠️ Redundant coordinator layers (Service + Application)
- ⚠️ TUI app has too many responsibilities
- ⚠️ UI state duplication
- ⚠️ Scattered synchronization logic
- ⚠️ Unclear ownership of shared state

### **Summary:**
The architecture has a **solid foundation** (audio engine, MIDI, models) but **coordination layers need refactoring**. The core is production-ready; the TUI layer needs consolidation. With the recommended changes, this would easily be an **A- architecture**.

The biggest win would come from **eliminating the SamplerService/SamplerApplication redundancy** and **implementing proper reactive UI updates** instead of imperative widget manipulation.
