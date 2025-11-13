# TUI Application Restructure Proposal

## Vision: Unified TUI as Main Application

The TUI should become the **primary application interface**, replacing the split between `edit` and `run` commands. Users will have one unified app with two modes:

- **Edit Mode** (default): Build and modify sets, assign samples, test with preview audio
- **Play Mode** (toggle with `P`): Full MIDI integration, performance-ready with LED feedback

This creates a seamless workflow: **Edit → Test → Play → Edit** without restarting.

---

## Current Problems

### 1. Monolithic Structure (897 lines in one file)
The `edit.py` file contains everything:
- 4 custom widgets (`PadWidget`, `PadGrid`, `PadDetailsPanel`, and their CSS)
- 3 modal screens (`FileBrowserScreen`, `SaveSetScreen`, `LoadSetScreen`)
- 1 main application class (`LaunchpadEditor`)
- 1 CLI command function
- Mixed business logic, state management, and presentation

### 2. Poor Integration with Existing Architecture
The edit command **doesn't leverage** the well-designed architecture:
- ❌ Doesn't use `SamplerApplication` facade (duplicates logic)
- ❌ Directly manages `SamplerEngine` and `AudioDevice` (reimplements lifecycle)
- ❌ Manual sample loading instead of using core layer methods
- ❌ No separation between preview playback and editing state
- ❌ Separate `run` and `edit` commands create fragmented user experience

**Example of duplication** (lines 569-586):
```python
# edit.py reimplements what SamplerApplication already does
devices, _ = AudioDevice.list_output_devices()
device_id = self.config.default_audio_device or devices[0][0]
self.audio_device = AudioDevice(device=device_id, buffer_size=512)
self.preview_engine = SamplerEngine(self.audio_device, num_pads=64)

# Load all samples into engine
for i, pad in enumerate(self.launchpad.pads):
    if pad.is_assigned:
        self.preview_engine.load_sample(i, pad)

self.preview_engine.start()
```

**Compare to how `run.py` does it** (clean and simple):
```python
app = SamplerApplication(config=config)
app.load_set(set_name)
app.start()
```

### 3. Tight Coupling and No Reusability
- Widgets directly access `self.app` methods (tight coupling)
- Screens can't be reused in other contexts
- Business logic embedded in UI event handlers
- No clear component boundaries

### 4. State Management Scattered
- `LaunchpadEditor` manages: launchpad state, selected pad, audio engine
- `PadDetailsPanel` tracks: selected_pad_index
- `PadGrid` maintains: pad_widgets dict
- No single source of truth

### 5. Mixed Presentation and Business Logic
Event handlers combine:
- UI updates (grid.update_pad, details.update_for_pad)
- Business logic (pad.sample = sample, pad.mode = mode)
- Audio management (engine.load_sample, engine.trigger_pad)
- No separation of concerns

---

## Proposed Architecture

### Directory Structure
```
src/launchsampler/
├── tui/                          # New: All Textual UI components
│   ├── __init__.py
│   ├── app.py                    # Main unified TUI application
│   ├── modes/                    # Mode system (Edit/Play)
│   │   ├── __init__.py
│   │   ├── base.py               # Base mode interface
│   │   ├── edit_mode.py          # Edit mode handler
│   │   └── play_mode.py          # Play mode handler
│   ├── services/                 # Business logic layer
│   │   ├── __init__.py
│   │   ├── editor_service.py     # Editing operations (assign, clear, etc.)
│   │   └── sampler_service.py    # Unified audio/MIDI using SamplerApplication
│   ├── widgets/                  # Reusable widgets
│   │   ├── __init__.py
│   │   ├── pad_widget.py         # Single pad display (with play state)
│   │   ├── pad_grid.py           # 8x8 grid container
│   │   ├── pad_details.py        # Details panel (mode-aware)
│   │   └── status_bar.py         # Status bar (mode, MIDI, voices)
│   ├── screens/                  # Modal screens
│   │   ├── __init__.py
│   │   ├── file_browser.py       # File selection
│   │   ├── save_set.py           # Save dialog
│   │   └── load_set.py           # Load dialog
│   └── styles/                   # CSS stylesheets
│       ├── __init__.py
│       └── default.tcss          # Shared styles
├── cli/
│   └── commands/
│       ├── run.py                # Main command (launches TUI)
│       └── edit.py               # Deprecated/alias to run
└── ... (existing structure)
```

### Key Design Principles

#### 1. **Separation of Concerns**
- **Presentation**: Widgets and screens only handle display and user input
- **Business Logic**: Services handle operations (assign sample, change mode, save)
- **Core Integration**: Services delegate to existing `SamplerApplication` and models

#### 2. **Reuse Existing Architecture**
- Use `SamplerApplication` for preview audio (don't reimplement)
- Delegate sample loading, playback, and lifecycle to core layer
- Models remain the single source of truth

#### 3. **Loose Coupling**
- Widgets communicate through events (not direct method calls)
- Services expose clean APIs
- Components are independently testable

#### 4. **Single Responsibility**
Each component has one job:
- `EditorService`: Manages editing operations on Launchpad model
- `SamplerService`: Wraps `SamplerApplication` for both preview and play modes
- `EditMode` / `PlayMode`: Handle mode-specific behaviors
- `PadWidget`: Displays a single pad's state (visual + play state)
- `PadGrid`: Arranges widgets in 8x8 layout
- `PadDetailsPanel`: Shows details and controls for selected pad
- `StatusBar`: Displays mode, MIDI connection, active voices
- `LaunchpadSampler`: Coordinates components, modes, and lifecycle

---

## Detailed Component Design

### 1. Service Layer

#### `EditorService` - Business Logic
```python
class EditorService:
    """Manages editing operations on a Launchpad configuration."""

    def __init__(self, launchpad: Launchpad, config: AppConfig):
        self.launchpad = launchpad
        self.config = config
        self.selected_pad_index: Optional[int] = None

    def select_pad(self, pad_index: int) -> Pad:
        """Select a pad and return its state."""
        self.selected_pad_index = pad_index
        return self.launchpad.pads[pad_index]

    def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
        """Assign a sample to a pad."""
        sample = Sample.from_file(sample_path)
        pad = self.launchpad.pads[pad_index]
        pad.sample = sample
        pad.volume = 0.8
        if not pad.is_assigned or pad.mode is None:
            pad.mode = PlaybackMode.ONE_SHOT
            pad.color = pad.mode.get_default_color()
        return pad

    def clear_pad(self, pad_index: int) -> Pad:
        """Clear a pad."""
        old_pad = self.launchpad.pads[pad_index]
        new_pad = Pad.empty(old_pad.x, old_pad.y)
        self.launchpad.pads[pad_index] = new_pad
        return new_pad

    def set_pad_mode(self, pad_index: int, mode: PlaybackMode) -> Pad:
        """Change pad playback mode."""
        pad = self.launchpad.pads[pad_index]
        if pad.is_assigned:
            pad.mode = mode
            pad.color = mode.get_default_color()
        return pad

    def save_set(self, name: str) -> Path:
        """Save current launchpad as a set."""
        self.config.ensure_directories()
        set_obj = Set(name=name, launchpad=self.launchpad)
        set_path = self.config.sets_dir / f"{name}.json"
        set_obj.save_to_file(set_path)
        return set_path

    def load_set(self, set_path: Path) -> Set:
        """Load a set from disk."""
        set_obj = Set.load_from_file(set_path)
        self.launchpad = set_obj.launchpad
        return set_obj
```

#### `SamplerService` - Unified Audio/MIDI Service
```python
class SamplerService:
    """Manages sampler application with Edit and Play modes."""

    def __init__(self, launchpad: Launchpad, config: AppConfig, on_pad_event=None):
        self.launchpad = launchpad
        self.config = config
        self._on_pad_event = on_pad_event  # Callback for visual feedback
        self._app: Optional[SamplerApplication] = None
        self._mode: Literal["stopped", "edit", "play"] = "stopped"

    def start_edit_mode(self) -> bool:
        """Start audio-only preview (edit mode - no MIDI)."""
        try:
            self._app = SamplerApplication(config=self.config)
            self._app.launchpad = self.launchpad

            # Start only audio engine (not MIDI controller)
            self._app._audio_device = AudioDevice(
                device=self.config.default_audio_device,
                buffer_size=512  # Low latency for preview
            )
            self._app._engine = SamplerEngine(self._app._audio_device, num_pads=64)

            # Load all samples
            for i, pad in enumerate(self.launchpad.pads):
                if pad.is_assigned:
                    self._app._engine.load_sample(i, pad)

            self._app._engine.start()
            self._app._is_running = True
            self._mode = "edit"
            return True
        except Exception as e:
            logger.error(f"Failed to start edit mode: {e}")
            return False

    def start_play_mode(self) -> bool:
        """Upgrade to play mode (add MIDI to running audio)."""
        if self._mode == "edit" and self._app:
            # Upgrade: add MIDI controller to running audio
            try:
                self._app._controller = LaunchpadController(
                    poll_interval=self.config.midi_poll_interval
                )
                self._app._controller.on_pad_pressed(self._handle_pad_pressed)
                self._app._controller.on_pad_released(self._handle_pad_released)
                self._app._controller.start()

                self._mode = "play"
                return True
            except Exception as e:
                logger.error(f"Failed to start play mode: {e}")
                return False
        elif self._mode == "stopped":
            # Cold start in play mode (full SamplerApplication)
            try:
                self._app = SamplerApplication(
                    config=self.config,
                    on_pad_event=self._on_pad_event
                )
                self._app.launchpad = self.launchpad
                self._app.start()  # Full start with MIDI
                self._mode = "play"
                return True
            except Exception as e:
                logger.error(f"Failed to start play mode: {e}")
                return False
        return False

    def stop_play_mode(self) -> bool:
        """Downgrade to edit mode (remove MIDI, keep audio)."""
        if self._mode == "play" and self._app and self._app._controller:
            self._app._controller.stop()
            self._app._controller = None
            self._mode = "edit"
            return True
        return False

    def stop(self) -> None:
        """Stop everything."""
        if self._app:
            self._app.stop()
            self._mode = "stopped"

    def trigger_pad(self, pad_index: int) -> None:
        """Trigger pad (works in both modes)."""
        if self._app and self._app._engine:
            self._app._engine.trigger_pad(pad_index)

    def reload_pad(self, pad_index: int) -> None:
        """Reload pad after editing."""
        if self._app and self._app._engine:
            pad = self.launchpad.pads[pad_index]
            if pad.is_assigned:
                self._app._engine.load_sample(pad_index, pad)
            else:
                self._app._engine.unload_sample(pad_index)

    def reload_all(self) -> None:
        """Reload all pads (after loading a set)."""
        if self._app and self._app._engine:
            for i, pad in enumerate(self.launchpad.pads):
                self.reload_pad(i)

    def stop_all(self) -> None:
        """Stop all playback."""
        if self._app and self._app._engine:
            self._app._engine.stop_all()

    def _handle_pad_pressed(self, pad_index: int) -> None:
        """Handle MIDI pad press (play mode only)."""
        if self._on_pad_event:
            self._on_pad_event("pressed", pad_index)

    def _handle_pad_released(self, pad_index: int) -> None:
        """Handle MIDI pad release (play mode only)."""
        if self._on_pad_event:
            self._on_pad_event("released", pad_index)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_connected(self) -> bool:
        """Check if MIDI is connected (play mode)."""
        return self._app and self._app.is_connected if self._mode == "play" else False

    @property
    def active_voices(self) -> int:
        """Get active voice count."""
        return self._app.active_voices if self._app else 0
```

### 2. Widget Layer

#### `PadWidget` - Presentation Only
```python
class PadWidget(Static):
    """Widget representing a single pad (presentation only)."""

    DEFAULT_CSS = """..."""  # Same as before

    def __init__(self, pad_index: int, pad: Pad) -> None:
        super().__init__()
        self.pad_index = pad_index
        self._pad = pad
        self.update_display()

    def update(self, pad: Pad) -> None:
        """Update display with new pad state."""
        self._pad = pad
        self.update_display()

    def update_display(self) -> None:
        """Render current state."""
        # Same rendering logic as before
        self.remove_class("one_shot", "loop", "hold", "empty")
        if self._pad.is_assigned:
            name = self._pad.sample.name[:6] if self._pad.sample else "???"
            self.update(f"[b]{self.pad_index}[/b]\n{name}")
            self.add_class(self._pad.mode.value)
        else:
            self.update(f"[dim]{self.pad_index}[/dim]\n—")
            self.add_class("empty")

    def on_click(self) -> None:
        """Post event when clicked (don't call app directly!)."""
        self.post_message(self.Selected(self.pad_index))

    class Selected(Message):
        """Message posted when pad is clicked."""
        def __init__(self, pad_index: int):
            super().__init__()
            self.pad_index = pad_index
```

#### `PadGrid` - Layout Container
```python
class PadGrid(Container):
    """8x8 grid of pad widgets (layout only)."""

    DEFAULT_CSS = """..."""  # Same as before

    def __init__(self, launchpad: Launchpad) -> None:
        super().__init__()
        self.launchpad = launchpad
        self.pad_widgets: dict[int, PadWidget] = {}

    def compose(self) -> ComposeResult:
        """Create grid (same as before)."""
        for y in range(7, -1, -1):
            for x in range(8):
                i = y * 8 + x
                pad = self.launchpad.pads[i]
                widget = PadWidget(i, pad)
                self.pad_widgets[i] = widget
                yield widget

    def update_pad(self, pad_index: int, pad: Pad) -> None:
        """Update a specific pad's display."""
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].update(pad)

    def select_pad(self, pad_index: int) -> None:
        """Visually mark selection."""
        for widget in self.pad_widgets.values():
            widget.remove_class("selected")
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].add_class("selected")

    def on_pad_widget_selected(self, message: PadWidget.Selected) -> None:
        """Forward pad selection events up."""
        self.post_message(self.PadSelected(message.pad_index))

    class PadSelected(Message):
        """Message posted when any pad is selected."""
        def __init__(self, pad_index: int):
            super().__init__()
            self.pad_index = pad_index
```

### 3. Application Coordinator

#### `LaunchpadSampler` - Unified Application
```python
class LaunchpadSampler(App):
    """Unified TUI application with Edit and Play modes."""

    TITLE = "Launchpad Sampler"

    BINDINGS = [
        Binding("e", "switch_mode('edit')", "Edit Mode"),
        Binding("p", "switch_mode('play')", "Play Mode"),
        Binding("s", "save", "Save"),
        Binding("l", "load", "Load"),
        Binding("b", "browse_sample", "Browse"),
        Binding("t", "test_pad", "Test"),
        Binding("escape", "stop_audio", "Stop"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: AppConfig, set_name: Optional[str] = None,
                 start_mode: str = "edit"):
        super().__init__()
        self.config = config
        self.set_name = set_name or "untitled"
        self._current_mode = start_mode

        # Load launchpad
        self.launchpad = self._load_initial_launchpad(set_name)

        # Services
        self.editor = EditorService(self.launchpad, config)
        self.sampler = SamplerService(
            self.launchpad,
            config,
            on_pad_event=self._on_pad_event
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PadGrid(self.launchpad)
            yield PadDetailsPanel()
        yield StatusBar()  # Shows: mode, MIDI status, active voices
        yield Footer()

    def on_mount(self) -> None:
        """Start in configured mode."""
        if self._current_mode == "edit":
            self._enter_edit_mode()
        elif self._current_mode == "play":
            self._enter_play_mode()

        # Select default pad
        self.editor.select_pad(0)
        self._update_ui_for_selection(0)

    def action_switch_mode(self, mode: str) -> None:
        """Switch between edit and play modes."""
        if mode == "play" and self._current_mode == "edit":
            self._enter_play_mode()
        elif mode == "edit" and self._current_mode == "play":
            self._exit_play_mode()

    def _enter_edit_mode(self) -> None:
        """Enter edit mode (audio preview only)."""
        if self.sampler.start_edit_mode():
            self._current_mode = "edit"
            self.sub_title = "Edit Mode"
            self.notify("✏ EDIT MODE - Press [P] for play mode")
            self._enable_edit_controls()
            self._update_status_bar()
        else:
            self.notify("Failed to start edit mode", severity="error")

    def _enter_play_mode(self) -> None:
        """Enter play mode (full MIDI integration)."""
        if self.sampler.start_play_mode():
            self._current_mode = "play"
            self.sub_title = "Play Mode"
            self.notify("▶ PLAY MODE - Physical Launchpad active")
            self._disable_edit_controls()
            self._update_status_bar()
        else:
            self.notify("Failed to start play mode", severity="error")

    def _exit_play_mode(self) -> None:
        """Exit play mode (back to edit mode)."""
        if self.sampler.stop_play_mode():
            self._current_mode = "edit"
            self.sub_title = "Edit Mode"
            self.notify("■ EDIT MODE - MIDI disabled")
            self._enable_edit_controls()
            self._update_status_bar()

    def _on_pad_event(self, event_type: str, pad_index: int) -> None:
        """Handle pad events from MIDI (for visual feedback)."""
        # Animate pad in TUI when triggered via physical Launchpad
        grid = self.query_one(PadGrid)
        if event_type == "pressed":
            grid.animate_pad_trigger(pad_index)

    def on_pad_grid_pad_selected(self, message: PadGrid.PadSelected) -> None:
        """Handle pad selection (edit mode only)."""
        if self._current_mode == "edit":
            pad = self.editor.select_pad(message.pad_index)
            self._update_ui_for_selection(message.pad_index)
        else:
            self.notify("Switch to edit mode to modify pads", severity="warning")

    def action_browse_sample(self) -> None:
        """Assign sample to pad (edit mode only)."""
        if self._current_mode != "edit":
            self.notify("Switch to edit mode first", severity="warning")
            return

        if self.editor.selected_pad_index is None:
            self.notify("Select a pad first", severity="warning")
            return

        def handle_file(file_path: Optional[Path]) -> None:
            if file_path:
                try:
                    pad = self.editor.assign_sample(
                        self.editor.selected_pad_index,
                        file_path
                    )
                    self.sampler.reload_pad(self.editor.selected_pad_index)
                    self._update_ui_for_pad(self.editor.selected_pad_index, pad)
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

        self.push_screen(FileBrowserScreen(self.config.samples_dir), handle_file)

    def action_save(self) -> None:
        """Save current set."""
        def handle_save(name: Optional[str]) -> None:
            if name:
                try:
                    self.editor.save_set(name)
                    self.set_name = name
                    self.notify(f"Saved set: {name}")
                except Exception as e:
                    self.notify(f"Error saving: {e}", severity="error")

        self.push_screen(SaveSetScreen(self.set_name), handle_save)

    def action_load(self) -> None:
        """Load a saved set."""
        def handle_load(set_path: Optional[Path]) -> None:
            if set_path:
                try:
                    set_obj = self.editor.load_set(set_path)
                    self.launchpad = set_obj.launchpad
                    self.sampler.launchpad = self.launchpad
                    self.sampler.reload_all()

                    # Update UI
                    grid = self.query_one(PadGrid)
                    for i in range(64):
                        grid.update_pad(i, self.launchpad.pads[i])

                    self.set_name = set_obj.name
                    self.notify(f"Loaded set: {set_obj.name}")
                except Exception as e:
                    self.notify(f"Error loading: {e}", severity="error")

        self.push_screen(LoadSetScreen(self.config.sets_dir), handle_load)

    def _enable_edit_controls(self) -> None:
        """Enable edit mode controls."""
        details = self.query_one(PadDetailsPanel)
        details.set_mode("edit")

    def _disable_edit_controls(self) -> None:
        """Disable edit mode controls."""
        details = self.query_one(PadDetailsPanel)
        details.set_mode("play")

    def _update_status_bar(self) -> None:
        """Update status bar with current mode and state."""
        status = self.query_one(StatusBar)
        status.update(
            mode=self._current_mode,
            connected=self.sampler.is_connected,
            voices=self.sampler.active_voices
        )

    def _update_ui_for_selection(self, pad_index: int) -> None:
        """Update UI after pad selection."""
        pad = self.launchpad.pads[pad_index]
        self.query_one(PadGrid).select_pad(pad_index)
        self.query_one(PadDetailsPanel).update_for_pad(pad_index, pad)

    def _update_ui_for_pad(self, pad_index: int, pad: Pad) -> None:
        """Update UI after pad modification."""
        self.query_one(PadGrid).update_pad(pad_index, pad)
        self.query_one(PadDetailsPanel).update_for_pad(pad_index, pad)

    def on_unmount(self) -> None:
        """Cleanup on exit."""
        self.sampler.stop()
```

### 4. CLI Commands

#### Main Command: `run` (launches TUI)
```python
# cli/commands/run.py
@click.command()
@click.option('--set', '-s', type=str, default=None,
              help='Name of saved set to load')
@click.option('--mode', '-m', type=click.Choice(['edit', 'play']), default='edit',
              help='Start in edit or play mode')
@click.option('--samples-dir', type=click.Path(...), default=None,
              help='Samples directory (ignored if --set is used)')
def run(set: Optional[str], mode: str, samples_dir: Optional[Path]):
    """
    Launch Launchpad Sampler TUI.

    The TUI has two modes:
    - Edit Mode (default): Build sets, assign samples, test with preview audio
    - Play Mode: Full MIDI integration for performance

    Switch modes anytime with E (edit) or P (play).

    Examples:
        # Start in edit mode
        launchsampler run --set my-drums

        # Start in play mode
        launchsampler run --set my-drums --mode play

        # Load from samples directory
        launchsampler run --samples-dir ./samples
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s',
        filename='launchsampler.log'
    )

    # Load config
    config = AppConfig.load_or_default()
    if samples_dir:
        config.samples_dir = samples_dir

    # Launch TUI
    from launchsampler.tui.app import LaunchpadSampler
    app = LaunchpadSampler(config, set_name=set, start_mode=mode)
    app.run()
```

#### Legacy Command: `edit` (alias/deprecated)
```python
# cli/commands/edit.py
@click.command()
@click.option('--set', '-s', type=str, default=None)
@click.option('--samples-dir', type=click.Path(...), default=None)
def edit(set: Optional[str], samples_dir: Optional[Path]):
    """
    DEPRECATED: Use 'launchsampler run' instead.

    This command is now an alias for 'launchsampler run --mode edit'.
    """
    click.echo("Note: 'edit' command is deprecated. Use 'launchsampler run' instead.")

    # Delegate to run command
    from .run import run as run_cmd
    ctx = click.get_current_context()
    ctx.invoke(run_cmd, set=set, mode='edit', samples_dir=samples_dir)
```

---

## Benefits of This Restructure

### 1. ✅ Unified User Experience
- **One app, two modes**: Edit → Test → Play → Edit (no restarts)
- **Seamless workflow**: Build sets visually, test with MIDI instantly
- **Single command**: `launchsampler run` for everything
- **No confusion**: Clear mode indicators, easy switching

### 2. ✅ Reuses Existing Architecture
- `SamplerService` wraps `SamplerApplication` (no duplication)
- Properly leverages core layer for both edit and play
- Models remain single source of truth
- Consistent with the rest of the codebase

### 3. ✅ Clean Separation of Concerns
- **Services**: Business logic (editing, audio/MIDI management)
- **Modes**: Mode-specific behaviors (edit vs play)
- **Widgets**: Pure presentation (display state, visual feedback)
- **App**: Orchestration (coordinate services ↔ UI ↔ modes)

### 4. ✅ Full MIDI Integration
- **Edit mode**: Audio preview only, won't interfere with editing
- **Play mode**: Physical Launchpad works, LED feedback, real-time response
- **Visual + Physical**: TUI shows state while hardware plays
- **Graceful degradation**: Works without MIDI device connected

### 5. ✅ Highly Reusable
- Widgets can be used in other TUI apps
- Services can be tested independently
- Screens are self-contained
- Mode system can be extended (e.g., record mode, performance mode)

### 6. ✅ Easier to Test
```python
# Test business logic without UI
def test_assign_sample():
    launchpad = Launchpad.create_empty()
    editor = EditorService(launchpad, config)

    pad = editor.assign_sample(0, Path("kick.wav"))

    assert pad.is_assigned
    assert pad.sample.name == "kick"

# Test mode transitions
def test_mode_switching():
    sampler = SamplerService(launchpad, config)

    assert sampler.start_edit_mode()
    assert sampler.mode == "edit"

    assert sampler.start_play_mode()
    assert sampler.mode == "play"
```

### 7. ✅ Better Maintainability
- Each file has ~100-200 lines (not 897)
- Clear component boundaries
- Easy to locate and modify features
- Mode-specific logic is isolated

### 8. ✅ Scalability
- Add new modes (record, performance, etc.)
- Add new widgets (waveform display, volume slider, velocity editor)
- Add new services (undo/redo, batch operations)
- Extend screens without affecting core logic
- Support multiple controller types (not just Launchpad)

---

## Migration Strategy

### Phase 1: Create Service Layer
1. Create `tui/services/editor_service.py`
2. Create `tui/services/sampler_service.py` with mode support
3. Move business logic from `LaunchpadEditor` to services
4. **Result**: Same UI, but business logic is separated

### Phase 2: Extract and Enhance Widgets
1. Move widgets to `tui/widgets/` (one file each)
2. Add `StatusBar` widget for mode/MIDI/voice display
3. Enhance `PadWidget` with play state animations
4. Update imports in app
5. **Result**: Reusable, mode-aware components

### Phase 3: Extract Screens
1. Move screens to `tui/screens/` (one file each)
2. Extract shared styles to `styles/default.tcss`
3. **Result**: Self-contained, reusable screens

### Phase 4: Implement Mode System
1. Create `tui/modes/base.py` (mode interface)
2. Create `tui/modes/edit_mode.py` and `play_mode.py`
3. Integrate mode switching into main app
4. **Result**: Clean mode separation

### Phase 5: Unify as Main Application
1. Rename `LaunchpadEditor` → `LaunchpadSampler`
2. Update `run.py` to launch TUI
3. Deprecate old `edit.py` command (or make it alias)
4. Add mode parameter to CLI
5. **Result**: Unified TUI as main interface

### Phase 6: Polish and Test
1. Add mode transition animations
2. Add MIDI connection indicators
3. Add active voice monitoring in status bar
4. Test mode switching edge cases
5. **Result**: Production-ready unified TUI

---

## Conclusion

### Current State Problems
The current `edit.py` is a **monolithic mess** that:
- 897 lines in one file with everything mixed together
- Duplicates logic from the well-designed core layer
- Separate `run` and `edit` commands create fragmented UX
- No MIDI integration in editor (missed opportunity)
- Hard to test, maintain, and extend

### Proposed Solution
Transform the TUI into the **unified main application** that:
- **Unifies** edit and runtime into one seamless experience
- **Respects** the existing architecture patterns (uses `SamplerApplication`)
- **Separates** concerns into services, widgets, modes, and orchestration
- **Enables** both visual editing and physical performance in one app
- **Provides** a clean, testable, and extensible foundation

### The Vision
```
┌──────────────────────────────────────────────────────────┐
│  One App, Two Modes, Complete Workflow                  │
│                                                          │
│  Edit Mode:  Build sets, assign samples, preview audio  │
│       ↓                                                  │
│  [Press P]   Switch to play mode                        │
│       ↓                                                  │
│  Play Mode:  Full MIDI, LED feedback, performance-ready │
│       ↓                                                  │
│  [Press E]   Back to editing                            │
│                                                          │
│  No restarts. No separate commands. Just flow.          │
└──────────────────────────────────────────────────────────┘
```

**This transforms the TUI from a simple editor into the primary interface for Launchpad Sampler, providing a unified, professional, and extensible application that leverages your excellent core architecture.**
