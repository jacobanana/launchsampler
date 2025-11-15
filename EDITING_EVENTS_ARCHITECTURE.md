# Editing Events Architecture - Analysis & Proposal

**Date:** November 15, 2025
**Context:** TUI application has significant overhead with manual `_reload_pad()` and `_refresh_pad_ui()` calls after every editing operation.

---

## 1. Current Architecture Analysis

### 1.1 Current Event Flow

The application currently has **TWO separate event systems** that don't talk to each other:

#### Playback Events (Audio → UI)
- **Observer Pattern:** `StateObserver` protocol → `SamplerStateMachine` → `Player` → `TUI App`
- **Events:** `NOTE_ON`, `NOTE_OFF`, `PAD_TRIGGERED`, `PAD_PLAYING`, `PAD_STOPPED`, `PAD_FINISHED`
- **Flow:** Audio thread → State machine → Observers → UI updates
- **Status:** ✅ **WORKS WELL** - Clean, decoupled, thread-safe

#### Editing Operations (UI → Audio)
- **Current Pattern:** Direct method calls + manual synchronization
- **Flow:** UI action → `EditorService` method → **Manual** `_reload_pad()` → **Manual** `_refresh_pad_ui()`
- **Status:** ❌ **PROBLEMATIC** - Repetitive, error-prone, tightly coupled

### 1.2 Problem Manifestation

Every editing operation in `app.py` follows this pattern:

```python
# Example: assign_sample action
pad = self.editor.assign_sample(selected_pad, file_path)
self._reload_pad(selected_pad)                    # ← Manual audio sync
self._sync_pad_ui(selected_pad, pad)              # ← Manual UI sync
```

**Occurrences in codebase:**
- `_reload_pad()`: **20 call sites**
- `_refresh_pad_ui()`: **6 call sites**
- `_sync_pad_ui()`: Multiple call sites

**Issues:**
1. **Boilerplate overhead** - Same 2-3 lines after every edit
2. **Easy to forget** - No compiler enforcement
3. **Inconsistent application** - Some paths might miss sync
4. **Tight coupling** - UI knows about audio engine internals
5. **No reusability** - Can't use `EditorService` without UI context

### 1.3 What Currently Works

The **playback event system** is exemplary:

```python
# Audio engine detects state change
self._state_machine.on_pad_playing(pad_index)

# Observers automatically notified
def on_playback_event(self, event: PlaybackEvent, pad_index: int):
    if event == PlaybackEvent.PAD_PLAYING:
        self._set_pad_playing_ui(pad_index, True)
```

**Why it works:**
- ✅ Decoupled: Audio engine doesn't know about UI
- ✅ Observable: Multiple observers can react
- ✅ Thread-safe: Events marshaled correctly
- ✅ Automatic: No manual sync needed
- ✅ Extensible: New observers easy to add

---

## 2. Root Cause Analysis

### 2.1 Asymmetric Architecture

| Aspect | Playback (Audio→UI) | Editing (UI→Audio) |
|--------|---------------------|---------------------|
| Pattern | Observer/Event-driven | Direct method calls |
| Coupling | Loose | Tight |
| Synchronization | Automatic | Manual |
| Consistency | Enforced by system | Developer discipline |
| Reusability | High | Low |

### 2.2 Missing Abstraction

`EditorService` is a **passive data manipulator**, not an **active event source**:

```python
# Current: EditorService just mutates data
def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
    pad.sample = Sample.from_file(sample_path)
    return pad  # ← Returns pad, caller must sync everything

# Desired: EditorService publishes events
def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
    pad.sample = Sample.from_file(sample_path)
    self._notify_observers(EditEvent.PAD_ASSIGNED, pad_index, pad)  # ← Automatic
    return pad
```

---

## 3. Proposed Architecture

### 3.1 Core Concept: Mirror the Playback Pattern

Introduce an **editing event system** that mirrors the successful playback event system:

```
┌─────────────────────────────────────────────────────────────┐
│                      EDITING EVENTS                         │
│                                                             │
│  User Action → EditorService → EditEvent → Observers       │
│                     ↓                          ↓            │
│                  Data Model            [Player, UI, ...]   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    PLAYBACK EVENTS                          │
│                                                             │
│  Audio Thread → StateMachine → PlaybackEvent → Observers   │
│                     ↓                            ↓          │
│                  Audio State             [UI, Logger, ...] │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 New Protocol: EditObserver

```python
# src/launchsampler/protocols.py

class EditEvent(Enum):
    """Events that occur during editing operations."""
    
    PAD_ASSIGNED = "pad_assigned"           # Sample assigned to pad
    PAD_CLEARED = "pad_cleared"             # Pad sample removed
    PAD_MOVED = "pad_moved"                 # Pad moved/swapped
    PAD_DUPLICATED = "pad_duplicated"       # Pad duplicated
    PAD_MODE_CHANGED = "pad_mode_changed"   # Playback mode changed
    PAD_VOLUME_CHANGED = "pad_volume_changed"  # Volume changed
    PAD_NAME_CHANGED = "pad_name_changed"   # Sample name changed
    PADS_CLEARED = "pads_cleared"           # Multiple pads cleared
    SET_LOADED = "set_loaded"               # New set loaded


@runtime_checkable
class EditObserver(Protocol):
    """Observer that receives editing events."""
    
    def on_edit_event(
        self, 
        event: EditEvent, 
        pad_indices: list[int],  # Can affect multiple pads (e.g., move)
        pads: list[Pad]          # The affected pad states
    ) -> None:
        """Handle editing events.
        
        Args:
            event: The type of editing event
            pad_indices: List of affected pad indices
            pads: List of affected pad states (post-edit)
        """
        ...
```

### 3.3 Enhanced EditorService

```python
# src/launchsampler/tui/services/editor_service.py

class EditorService:
    """Manages editing operations with event notifications."""
    
    def __init__(self, launchpad: Launchpad, config: AppConfig):
        self.launchpad = launchpad
        self.config = config
        self.selected_pad_index: Optional[int] = None
        self._clipboard: Optional[Pad] = None
        
        # Event system
        self._observers: list[EditObserver] = []
        self._event_lock = Lock()
    
    # --- Observer Management ---
    
    def register_observer(self, observer: EditObserver) -> None:
        """Register observer for edit events."""
        with self._event_lock:
            if observer not in self._observers:
                self._observers.append(observer)
    
    def unregister_observer(self, observer: EditObserver) -> None:
        """Unregister observer."""
        with self._event_lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def _notify_observers(
        self, 
        event: EditEvent, 
        pad_indices: list[int], 
        pads: list[Pad]
    ) -> None:
        """Notify all observers of an edit event."""
        with self._event_lock:
            for observer in self._observers:
                try:
                    observer.on_edit_event(event, pad_indices, pads)
                except Exception as e:
                    logger.error(f"Error notifying observer {observer}: {e}")
    
    # --- Modified Operations (examples) ---
    
    def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
        """Assign sample and notify observers."""
        self._validate_pad_index(pad_index)
        if not sample_path.exists():
            raise ValueError(f"Sample file not found: {sample_path}")
        
        sample = Sample.from_file(sample_path)
        pad = self.launchpad.pads[pad_index]
        pad.sample = sample
        pad.volume = 0.8
        
        if pad.mode is None:
            pad.mode = PlaybackMode.ONE_SHOT
            pad.color = pad.mode.get_default_color()
        
        # Notify observers
        self._notify_observers(EditEvent.PAD_ASSIGNED, [pad_index], [pad])
        
        logger.info(f"Assigned sample '{sample.name}' to pad {pad_index}")
        return pad
    
    def move_pad(
        self, 
        source_index: int, 
        target_index: int, 
        swap: bool = False
    ) -> tuple[Pad, Pad]:
        """Move pad and notify observers."""
        # ... validation and move logic ...
        
        # Notify observers about BOTH affected pads
        self._notify_observers(
            EditEvent.PAD_MOVED,
            [source_index, target_index],
            [source_pad, target_pad]
        )
        
        return (source_pad, target_pad)
    
    # Similar pattern for: clear_pad, set_pad_mode, set_pad_volume, etc.
```

### 3.4 Automatic Handlers

#### Audio Handler (in Player)

```python
# src/launchsampler/core/player.py

class Player(StateObserver, EditObserver):  # ← Implements both protocols
    """Player that observes both playback and editing events."""
    
    def __init__(self, config: AppConfig):
        # ... existing init ...
    
    # --- EditObserver Protocol ---
    
    def on_edit_event(
        self, 
        event: EditEvent, 
        pad_indices: list[int], 
        pads: list[Pad]
    ) -> None:
        """Handle editing events and sync audio engine."""
        if not self._engine:
            return
        
        for pad_index, pad in zip(pad_indices, pads):
            if event in (
                EditEvent.PAD_ASSIGNED, 
                EditEvent.PAD_MOVED,
                EditEvent.PAD_DUPLICATED,
                EditEvent.PAD_MODE_CHANGED
            ):
                # Reload sample into engine
                if pad.is_assigned:
                    self._engine.load_sample(pad_index, pad)
                else:
                    self._engine.unload_sample(pad_index)
            
            elif event == EditEvent.PAD_CLEARED:
                # Unload sample
                self._engine.unload_sample(pad_index)
            
            elif event == EditEvent.PAD_VOLUME_CHANGED:
                # Update volume without reloading
                self._engine.update_pad_volume(pad_index, pad.volume)
            
            elif event == EditEvent.SET_LOADED:
                # Reload entire set
                self._load_set_into_engine(pads[0])  # pads[0] is the Set
```

#### UI Handler (in TUI App)

```python
# src/launchsampler/tui/app.py

class LaunchpadSampler(App, EditObserver):  # ← Implements EditObserver
    """TUI that observes editing events."""
    
    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # ... existing mount logic ...
        
        # Register as edit observer
        self.editor.register_observer(self)
    
    # --- EditObserver Protocol ---
    
    def on_edit_event(
        self, 
        event: EditEvent, 
        pad_indices: list[int], 
        pads: list[Pad]
    ) -> None:
        """Handle editing events and update UI."""
        for pad_index, pad in zip(pad_indices, pads):
            if event == EditEvent.SET_LOADED:
                # Full UI refresh
                self._reload_set_ui(pads[0])  # pads[0] is the Set
            else:
                # Update specific pad(s)
                self._update_pad_ui(pad_index, pad)
    
    def _update_pad_ui(self, pad_index: int, pad: Pad) -> None:
        """Update UI for a single pad."""
        grid = self.query_one(PadGrid)
        grid.update_pad(pad_index, pad)
        
        # Update details if this pad is selected
        if pad_index == self.editor.selected_pad_index:
            audio_data = None
            if self.player._engine and pad.is_assigned:
                audio_data = self.player._engine.get_audio_data(pad_index)
            
            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(pad_index, pad, audio_data=audio_data)
    
    # --- Simplified Actions ---
    
    @edit_only
    def action_browse_sample(self) -> None:
        """Open file browser to assign a sample."""
        if self.editor.selected_pad_index is None:
            self.notify("Select a pad first", severity="warning")
            return
        
        selected_pad = self.editor.selected_pad_index
        
        def handle_file(file_path: Optional[Path]) -> None:
            if file_path:
                try:
                    # Just call editor - events handle the rest!
                    pad = self.editor.assign_sample(selected_pad, file_path)
                    # ↓ No more manual _reload_pad() or _refresh_pad_ui()!
                    
                    self.notify(f"Assigned: {pad.sample.name}")
                except Exception as e:
                    logger.error(f"Error assigning sample: {e}")
                    self.notify(f"Error: {e}", severity="error")
        
        browse_dir = self.current_set.samples_root or Path.home()
        self.push_screen(FileBrowserScreen(browse_dir), handle_file)
```

---

## 4. Benefits of Proposed Architecture

### 4.1 Code Reduction

**Before:**
```python
def action_copy_pad(self) -> None:
    pad = self.editor.copy_pad(selected_pad)
    self._reload_pad(selected_pad)          # ← Manual
    self._refresh_pad_ui(selected_pad, pad)  # ← Manual
    self.notify(f"Copied: {pad.sample.name}")
```

**After:**
```python
def action_copy_pad(self) -> None:
    pad = self.editor.copy_pad(selected_pad)
    # Events automatically sync audio & UI!
    self.notify(f"Copied: {pad.sample.name}")
```

**Reduction:** ~40% less code per action, 0 synchronization bugs

### 4.2 Consistency Guarantees

- ✅ **Impossible to forget** to sync audio/UI - the event system ensures it
- ✅ **Uniform behavior** - all edits follow same path
- ✅ **Centralized logic** - sync logic in one place (observers)

### 4.3 Extensibility

New observers can be added without modifying existing code:

```python
# Example: Logging observer
class EditLogger(EditObserver):
    def on_edit_event(self, event, pad_indices, pads):
        logger.info(f"Edit: {event.value} on pads {pad_indices}")

# Register
editor.register_observer(EditLogger())
```

### 4.4 Testability

EditorService can be tested in isolation without UI or audio:

```python
def test_assign_sample_fires_event():
    editor = EditorService(launchpad, config)
    observer = Mock(spec=EditObserver)
    editor.register_observer(observer)
    
    editor.assign_sample(0, Path("test.wav"))
    
    observer.on_edit_event.assert_called_once_with(
        EditEvent.PAD_ASSIGNED,
        [0],
        [editor.get_pad(0)]
    )
```

### 4.5 Decoupling

- `EditorService` doesn't know about `Player` or `App`
- `Player` doesn't know about `App`
- Each component only knows about the protocol interface

---

## 5. Implementation Plan

### Phase 1: Foundation (Low Risk)
**Goal:** Add event system without breaking existing code

1. **Add protocols to `protocols.py`**
   - Define `EditEvent` enum
   - Define `EditObserver` protocol
   - Add comprehensive docstrings

2. **Enhance `EditorService`**
   - Add observer registration methods
   - Add `_notify_observers()` helper
   - Keep existing methods unchanged initially

3. **Add unit tests**
   - Test observer registration/unregistration
   - Test event notification
   - Test that events are fired for each operation

**Deliverable:** Event system infrastructure, 100% backward compatible

### Phase 2: Implement Observers (Medium Risk)
**Goal:** Create handlers for edit events

1. **Create `EditHandler` in `Player`**
   - Implement `EditObserver` protocol in `Player`
   - Add `on_edit_event()` method
   - Route events to appropriate audio engine calls
   - Unit test audio sync behavior

2. **Create UI handler in `App`**
   - Implement `EditObserver` protocol in `LaunchpadSampler`
   - Add `on_edit_event()` method
   - Route events to UI update methods
   - Keep existing `_sync_pad_ui()` for now

3. **Register observers**
   - In `Player.start()`, register as observer on `EditorService`
   - In `App.on_mount()`, register as observer on `EditorService`

**Deliverable:** Observers that handle events (parallel to manual calls)

### Phase 3: Fire Events (Medium Risk)
**Goal:** Make EditorService fire events

1. **Update all EditorService methods**
   - `assign_sample()` → fires `PAD_ASSIGNED`
   - `clear_pad()` → fires `PAD_CLEARED`
   - `move_pad()` → fires `PAD_MOVED`
   - `set_pad_mode()` → fires `PAD_MODE_CHANGED`
   - `set_pad_volume()` → fires `PAD_VOLUME_CHANGED`
   - `set_sample_name()` → fires `PAD_NAME_CHANGED`
   - etc.

2. **Comprehensive testing**
   - Test that each operation fires correct event
   - Test that observers receive events
   - Test that audio and UI are updated

**Deliverable:** Events flowing through the system (alongside manual calls)

### Phase 4: Remove Manual Calls (Low Risk)
**Goal:** Clean up redundant code

1. **Remove manual `_reload_pad()` calls from `app.py`**
   - Search for all occurrences (20 locations)
   - Verify event handler covers same logic
   - Remove line by line

2. **Remove manual `_refresh_pad_ui()` calls**
   - Search for all occurrences (6 locations)
   - Verify UI handler covers same logic
   - Remove line by line

3. **Simplify helper methods**
   - `_reload_pad()` → delete (logic in observer)
   - `_refresh_pad_ui()` → delete (logic in observer)
   - Keep `_sync_pad_ui()` → rename to `_update_pad_ui()` (used by observer)

4. **Comprehensive testing**
   - Run all existing tests
   - Manual TUI testing of all edit operations
   - Verify audio loads/unloads correctly
   - Verify UI updates correctly

**Deliverable:** Clean, event-driven codebase with no duplication

### Phase 5: Documentation & Polish (Low Risk)
**Goal:** Document and optimize

1. **Update documentation**
   - Document event flow in architecture docs
   - Add examples of implementing observers
   - Update inline comments

2. **Performance optimization**
   - Batch events if needed (e.g., SET_LOADED)
   - Profile event dispatch overhead
   - Add metrics/logging

3. **Final testing**
   - Integration tests
   - Performance tests
   - User acceptance testing

**Deliverable:** Production-ready event-driven editing system

---

## 6. Risk Assessment

### Low Risk
- Adding protocols (backward compatible)
- Adding observers (parallel system)
- Documentation updates

### Medium Risk
- Firing events from EditorService (could double-sync if not careful)
- Threading concerns (events from UI thread, observers need thread safety)
- Event ordering for multi-pad operations (move, swap)

### Mitigation Strategies

1. **Parallel deployment**
   - Keep manual calls initially
   - Run both systems in parallel
   - Verify identical behavior
   - Remove manual calls only when confident

2. **Thread safety**
   - Use `call_from_thread()` in UI observer if needed
   - Lock-free audio observer (events from UI thread anyway)
   - Document threading model clearly

3. **Testing**
   - Unit tests for every event type
   - Integration tests for complex operations
   - Manual testing of all UI flows

---

## 7. Alternative Approaches Considered

### 7.1 Signals/Slots (Qt-style)
**Pros:** Mature pattern, well-understood
**Cons:** Adds dependency, overkill for simple observer pattern
**Verdict:** ❌ Rejected - Observer protocol is sufficient

### 7.2 Message Bus
**Pros:** Ultimate decoupling, can add middleware
**Cons:** More complex, harder to debug, overkill
**Verdict:** ❌ Rejected - Too heavyweight

### 7.3 Reactive Streams (RxPY)
**Pros:** Powerful, composable, async-friendly
**Cons:** Steep learning curve, dependency, overkill
**Verdict:** ❌ Rejected - Simpler solution preferred

### 7.4 Keep Manual Calls, Add Helper
**Pros:** Minimal change, low risk
**Cons:** Doesn't solve fundamental problem, still error-prone
**Verdict:** ❌ Rejected - Doesn't address root cause

---

## 8. Success Criteria

The implementation will be considered successful when:

1. ✅ **Zero manual `_reload_pad()` calls** in `app.py`
2. ✅ **Zero manual `_refresh_pad_ui()` calls** in `app.py`
3. ✅ **All edit operations fire events** that observers handle
4. ✅ **Audio engine syncs automatically** on edits
5. ✅ **UI updates automatically** on edits
6. ✅ **All existing tests pass** with no modifications
7. ✅ **New tests cover all events** (100% coverage)
8. ✅ **Performance is same or better** (no regression)
9. ✅ **Code is cleaner** (less duplication, more maintainable)

---

## 9. Timeline Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Foundation | 4 hours | Low |
| Phase 2: Observers | 6 hours | Medium |
| Phase 3: Fire Events | 4 hours | Medium |
| Phase 4: Remove Manual Calls | 3 hours | Low |
| Phase 5: Documentation | 2 hours | Low |
| **Total** | **19 hours** | **Medium** |

**Recommendation:** Execute phases 1-3 in sequence, then pause for validation before phases 4-5.

---

## 10. Conclusion

The current architecture has an **asymmetry** between playback events (excellent) and editing operations (problematic). By introducing an **EditObserver protocol** and making `EditorService` an **event source**, we can:

1. Eliminate 20+ manual synchronization points
2. Guarantee consistency across all edit operations
3. Improve testability and maintainability
4. Enable future extensibility (logging, undo/redo, network sync, etc.)

The proposed architecture **mirrors the successful playback event pattern**, ensuring consistency and leveraging proven design. The implementation plan is **low-risk** with clear phases and rollback points.

**Recommendation:** Proceed with implementation.
