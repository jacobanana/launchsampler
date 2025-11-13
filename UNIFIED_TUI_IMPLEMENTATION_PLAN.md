# Unified TUI Implementation Plan

## Vision
A single TUI application that handles both editing and runtime playback with seamless mode switching.

```
Edit Mode (E) ←→ Play Mode (P)
    ↓                  ↓
Audio preview      Full MIDI + Audio
Click to test      Hardware control
No MIDI input      LED feedback
```

---

## Implementation Phases

### Phase 1: Create Foundation Structure
**Goal**: Set up the `tui/` package with basic structure (no breaking changes to existing code)

#### Tasks:
1. **Create directory structure**
   ```
   src/launchsampler/tui/
   ├── __init__.py
   ├── services/
   │   └── __init__.py
   ├── widgets/
   │   └── __init__.py
   ├── screens/
   │   └── __init__.py
   └── styles/
       └── __init__.py
   ```

2. **Keep `edit.py` working** - Don't break existing functionality yet

**Outcome**: Empty structure ready for migration

---

### Phase 2: Extract and Create SamplerService
**Goal**: Create the core service that wraps `SamplerApplication` with mode switching

#### Tasks:
1. **Create `tui/services/sampler_service.py`**
   ```python
   class SamplerService:
       """Manages audio + MIDI with mode switching."""

       def __init__(self, launchpad: Launchpad, config: AppConfig)
       def start_preview() -> bool              # Edit mode: audio only
       def start_play_mode() -> bool            # Play mode: audio + MIDI
       def stop_play_mode() -> bool             # Back to edit mode
       def trigger_pad(pad_index: int)          # Manual trigger
       def reload_pad(pad_index: int)           # After editing
       def stop()                               # Cleanup

       @property mode -> str                    # "edit" or "play"
       @property is_connected -> bool           # MIDI status
       @property active_voices -> int           # Voice count
   ```

2. **Key implementation details**:
   - Wraps `SamplerApplication` (no duplication)
   - `start_preview()`: Creates audio engine only (no MIDI controller)
   - `start_play_mode()`: Adds MIDI controller to existing audio
   - `stop_play_mode()`: Removes MIDI, keeps audio running
   - Handles callbacks for visual feedback in TUI

3. **Test the service independently**:
   ```python
   # Test script
   config = AppConfig.load_or_default()
   launchpad = Launchpad.create_empty()
   service = SamplerService(launchpad, config)

   # Test edit mode
   assert service.start_preview()
   assert service.mode == "edit"
   service.trigger_pad(0)

   # Test play mode
   assert service.start_play_mode()
   assert service.mode == "play"
   assert service.is_connected  # If Launchpad connected

   # Back to edit
   assert service.stop_play_mode()
   assert service.mode == "edit"
   ```

**Outcome**: Core service that handles audio/MIDI lifecycle with mode switching

---

### Phase 3: Extract EditorService
**Goal**: Separate business logic from UI

#### Tasks:
1. **Create `tui/services/editor_service.py`**
   ```python
   class EditorService:
       """Manages editing operations on Launchpad configuration."""

       def __init__(self, launchpad: Launchpad, config: AppConfig)
       def select_pad(pad_index: int) -> Pad
       def assign_sample(pad_index: int, sample_path: Path) -> Pad
       def clear_pad(pad_index: int) -> Pad
       def set_pad_mode(pad_index: int, mode: PlaybackMode) -> Pad
       def save_set(name: str) -> Path
       def load_set(set_path: Path) -> Set

       @property selected_pad_index -> Optional[int]
   ```

2. **Pure business logic** - No UI dependencies, easy to test

**Outcome**: Testable business logic layer

---

### Phase 4: Extract Widgets (One at a time)
**Goal**: Break up monolithic widgets into reusable components

#### 4a. Extract PadWidget
1. **Create `tui/widgets/pad_widget.py`**
   - Copy existing `PadWidget` from `edit.py`
   - Make it event-driven (emit `Selected` message instead of calling app)
   - Add method: `update(pad: Pad)` to refresh display
   - Keep all CSS in the widget

2. **Test independently**:
   ```python
   # Can render widget in isolation
   widget = PadWidget(0, pad)
   widget.update(new_pad_state)
   ```

#### 4b. Extract PadGrid
1. **Create `tui/widgets/pad_grid.py`**
   - Copy existing `PadGrid` from `edit.py`
   - Use the extracted `PadWidget`
   - Emit `PadSelected(pad_index)` messages
   - Method: `update_pad(pad_index: int, pad: Pad)`

#### 4c. Extract PadDetailsPanel
1. **Create `tui/widgets/pad_details.py`**
   - Copy existing `PadDetailsPanel` from `edit.py`
   - Keep button handling, emit events for actions
   - Method: `update_for_pad(pad_index: int, pad: Pad)`

#### 4d. Create StatusBar (New Widget)
1. **Create `tui/widgets/status_bar.py`**
   ```python
   class StatusBar(Static):
       """Shows mode, MIDI status, active voices."""

       def update_status(
           self,
           mode: str,
           is_connected: bool,
           active_voices: int
       ):
           # Display: "■ EDIT | ○ Disconnected | ♫ 0 voices"
           # or:      "▶ PLAY | ● Connected: Launchpad MK2 | ♫ 3 voices"
   ```

**Outcome**: Reusable, testable widgets in separate files

---

### Phase 5: Extract Screens
**Goal**: Move modal dialogs to separate files

#### Tasks:
1. **Create `tui/screens/file_browser.py`**
   - Copy `FileBrowserScreen` from `edit.py`
   - No changes needed (already self-contained)

2. **Create `tui/screens/save_set.py`**
   - Copy `SaveSetScreen` from `edit.py`

3. **Create `tui/screens/load_set.py`**
   - Copy `LoadSetScreen` from `edit.py`

**Outcome**: Clean modal screens in separate files

---

### Phase 6: Create Unified App
**Goal**: Build the main application with mode switching

#### Tasks:
1. **Create `tui/app.py`**
   ```python
   class LaunchpadSampler(App):
       """Unified TUI application."""

       TITLE = "Launchpad Sampler"

       BINDINGS = [
           Binding("e", "switch_mode('edit')", "Edit Mode"),
           Binding("p", "switch_mode('play')", "Play Mode"),
           Binding("s", "save", "Save"),
           Binding("l", "load", "Load"),
           Binding("b", "browse_sample", "Browse"),
           Binding("c", "clear_pad", "Clear"),
           Binding("t", "test_pad", "Test"),
           Binding("q", "quit", "Quit"),
           # Navigation
           Binding("up", "navigate_up", "Up", show=False),
           Binding("down", "navigate_down", "Down", show=False),
           Binding("left", "navigate_left", "Left", show=False),
           Binding("right", "navigate_right", "Right", show=False),
       ]

       def __init__(self, config: AppConfig, set_name: Optional[str] = None):
           super().__init__()
           self.config = config
           self.set_name = set_name or "untitled"
           self.launchpad = self._load_initial_launchpad()

           # Services
           self.editor = EditorService(self.launchpad, config)
           self.sampler = SamplerService(self.launchpad, config)

           self._current_mode = "edit"

       def compose(self) -> ComposeResult:
           yield Header()
           with Horizontal():
               yield PadGrid(self.launchpad)
               yield PadDetailsPanel()
           yield StatusBar()
           yield Footer()

       def on_mount(self) -> None:
           """Start in edit mode."""
           if self.sampler.start_preview():
               self.notify("Edit mode - Press [P] for play mode")
           self._update_status()

       def action_switch_mode(self, mode: str) -> None:
           """Switch between edit and play modes."""
           if mode == "play" and self._current_mode == "edit":
               if self.sampler.start_play_mode():
                   self._current_mode = "play"
                   self.sub_title = f"▶ PLAYING: {self.set_name}"
                   self.notify("▶ PLAY MODE - Hardware active")
                   self._disable_edit_controls()
                   self._update_status()

           elif mode == "edit" and self._current_mode == "play":
               if self.sampler.stop_play_mode():
                   self._current_mode = "edit"
                   self.sub_title = f"Editing: {self.set_name}"
                   self.notify("■ EDIT MODE - Hardware disabled")
                   self._enable_edit_controls()
                   self._update_status()

       def _disable_edit_controls(self) -> None:
           """Disable editing in play mode."""
           details = self.query_one(PadDetailsPanel)
           details.query_one("#browse-btn").disabled = True
           details.query_one("#clear-btn").disabled = True
           # ... disable other edit buttons

       def _enable_edit_controls(self) -> None:
           """Re-enable editing in edit mode."""
           # Opposite of above

       def _update_status(self) -> None:
           """Update status bar."""
           status = self.query_one(StatusBar)
           status.update_status(
               mode=self._current_mode,
               is_connected=self.sampler.is_connected,
               active_voices=self.sampler.active_voices
           )

       # ... rest of the event handlers
   ```

2. **Wire up all the components**:
   - Widgets communicate via messages
   - App coordinates between `EditorService` and `SamplerService`
   - Clear separation: UI → App → Services → Core

**Outcome**: Fully functional unified TUI

---

### Phase 7: Update CLI Command
**Goal**: Make the TUI the main entry point

#### Tasks:
1. **Update `cli/commands/edit.py`**:
   ```python
   @click.command()
   @click.option('--set', '-s', type=str, default=None)
   @click.option('--samples-dir', type=click.Path(...), default=None)
   @click.option('--play', is_flag=True, help='Start in play mode')
   def edit(set: Optional[str], samples_dir: Optional[Path], play: bool):
       """
       Launchpad Sampler - Unified editor and player.

       Edit Mode: Build and modify sample sets
       Play Mode: Full MIDI control and performance

       Toggle modes with [E] and [P] keys.
       """
       logging.basicConfig(
           level=logging.INFO,
           format='%(levelname)s - %(message)s',
           filename='launchsampler.log'
       )

       config = AppConfig.load_or_default()
       if samples_dir:
           config.samples_dir = samples_dir

       from launchsampler.tui.app import LaunchpadSampler
       app = LaunchpadSampler(config, set_name=set)

       # If --play flag, switch to play mode after startup
       if play:
           app._start_in_play_mode = True

       app.run()
   ```

2. **Deprecate or alias `run` command**:
   ```python
   # cli/commands/run.py
   @click.command()
   def run(**kwargs):
       """
       DEPRECATED: Use 'launchsampler edit --play' instead.

       This command is kept for backwards compatibility.
       """
       click.echo("Note: 'run' command is deprecated.")
       click.echo("Use: launchsampler edit --play")
       click.echo("")

       # Delegate to edit command with --play flag
       from .edit import edit
       ctx = click.get_current_context()
       ctx.invoke(edit, play=True, **kwargs)
   ```

**Outcome**: Clean CLI interface with unified command

---

### Phase 8: Polish and Features
**Goal**: Add nice-to-have features

#### Optional Enhancements:
1. **Visual feedback for MIDI triggers**:
   - Pads pulse/highlight when triggered via hardware
   - Active voice indicators on grid

2. **Live editing (advanced)**:
   - Allow sample assignment even in play mode
   - Hot-reload pads without stopping playback

3. **Keyboard shortcuts for modes**:
   - Number keys (1-8) to select mode presets
   - Shift+arrows for faster navigation

4. **Performance stats**:
   - Latency monitoring
   - Buffer underrun warnings
   - CPU usage

5. **Undo/Redo**:
   - Command pattern for edit operations
   - Ctrl+Z / Ctrl+Y support

**Outcome**: Polished, professional TUI

---

## Testing Strategy

### Unit Tests
```python
# Test services in isolation
def test_sampler_service_mode_switching():
    service = SamplerService(launchpad, config)
    assert service.start_preview()
    assert service.mode == "edit"
    assert service.start_play_mode()
    assert service.mode == "play"

def test_editor_service_assign_sample():
    editor = EditorService(launchpad, config)
    pad = editor.assign_sample(0, Path("kick.wav"))
    assert pad.is_assigned
    assert pad.sample.name == "kick"
```

### Integration Tests
```python
# Test app with mocked hardware
def test_mode_switching_ui():
    app = LaunchpadSampler(config)
    app.action_switch_mode("play")
    assert app._current_mode == "play"
    # Assert UI changes
```

### Manual Testing Checklist
- [ ] Edit mode: Assign samples, change modes, save sets
- [ ] Play mode: Physical Launchpad triggers audio
- [ ] Mode switching: Seamless transition between modes
- [ ] No MIDI interference in edit mode
- [ ] LED feedback in play mode
- [ ] Status bar updates correctly
- [ ] Active voice count accurate
- [ ] No audio glitches during mode switch

---

## Migration Path

### Backward Compatibility
1. Keep old `edit.py` as `edit_legacy.py` temporarily
2. Add CLI flag: `launchsampler edit --legacy` to use old version
3. After testing period, remove legacy version

### Data Compatibility
- Set files (`.json`) remain unchanged
- Config files remain unchanged
- No breaking changes to data formats

---

## File Size Comparison

**Before**:
- `cli/commands/edit.py`: 897 lines

**After**:
- `tui/app.py`: ~300 lines
- `tui/services/sampler_service.py`: ~150 lines
- `tui/services/editor_service.py`: ~100 lines
- `tui/widgets/pad_widget.py`: ~80 lines
- `tui/widgets/pad_grid.py`: ~80 lines
- `tui/widgets/pad_details.py`: ~120 lines
- `tui/widgets/status_bar.py`: ~50 lines
- `tui/screens/file_browser.py`: ~80 lines
- `tui/screens/save_set.py`: ~80 lines
- `tui/screens/load_set.py`: ~100 lines
- `cli/commands/edit.py`: ~50 lines (thin wrapper)

**Total**: ~1190 lines (vs 897 before)
**But**: Much cleaner, testable, maintainable, and reusable

---

## Timeline Estimate

- **Phase 1**: 30 minutes (structure setup)
- **Phase 2**: 2-3 hours (SamplerService - most complex)
- **Phase 3**: 1 hour (EditorService)
- **Phase 4**: 2-3 hours (Extract all widgets)
- **Phase 5**: 1 hour (Extract screens)
- **Phase 6**: 3-4 hours (Build unified app)
- **Phase 7**: 1 hour (CLI updates)
- **Phase 8**: 2-4 hours (Polish, optional)

**Total**: 12-18 hours of focused work

---

## Success Criteria

✅ Single TUI app handles both editing and playing
✅ Seamless mode switching (E ↔ P)
✅ No code duplication with `run` command
✅ Uses `SamplerApplication` properly
✅ Clean separation of concerns
✅ Each file < 300 lines
✅ Widgets are reusable
✅ Services are testable
✅ MIDI works only in play mode
✅ No breaking changes to data formats

---

## Next Immediate Steps

1. **Decide**: Do you want to start implementation now?
2. **If yes**: Which phase to start with? (I recommend Phase 1 → 2 → 3)
3. **If no**: Any questions or changes to the plan?
