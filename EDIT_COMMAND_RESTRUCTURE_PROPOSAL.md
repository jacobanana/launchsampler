# Edit Command Restructure Proposal

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
│   ├── app.py                    # Main LaunchpadEditor app
│   ├── services/                 # Business logic layer
│   │   ├── __init__.py
│   │   ├── editor_service.py     # Editing operations (assign, clear, etc.)
│   │   └── preview_service.py    # Audio preview using SamplerApplication
│   ├── widgets/                  # Reusable widgets
│   │   ├── __init__.py
│   │   ├── pad_widget.py         # Single pad display
│   │   ├── pad_grid.py           # 8x8 grid container
│   │   └── pad_details.py        # Details panel
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
│       └── edit.py               # Thin CLI command (orchestrates tui.app)
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
- `PreviewService`: Wraps `SamplerApplication` for preview playback
- `PadWidget`: Displays a single pad's state
- `PadGrid`: Arranges widgets in 8x8 layout
- `PadDetailsPanel`: Shows details and controls for selected pad
- `LaunchpadEditor`: Coordinates components and handles app lifecycle

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

#### `PreviewService` - Audio Preview
```python
class PreviewService:
    """Manages audio preview using SamplerApplication."""

    def __init__(self, launchpad: Launchpad, config: AppConfig):
        self.launchpad = launchpad
        self.config = config
        self._app: Optional[SamplerApplication] = None

    def start(self) -> bool:
        """Start preview engine (reuses SamplerApplication!)."""
        try:
            self._app = SamplerApplication(config=self.config)
            self._app.launchpad = self.launchpad
            self._app.start(buffer_size=512)  # Low latency for preview
            return True
        except Exception as e:
            logger.error(f"Failed to start preview: {e}")
            return False

    def stop(self) -> None:
        """Stop preview engine."""
        if self._app:
            self._app.stop()

    def trigger_pad(self, pad_index: int) -> None:
        """Test a pad."""
        if self._app and self._app.is_running:
            # SamplerApplication handles trigger internally
            pad = self.launchpad.pads[pad_index]
            if pad.is_assigned:
                self._app._engine.trigger_pad(pad_index)

    def reload_pad(self, pad_index: int) -> None:
        """Reload a pad after changes."""
        if self._app and self._app._engine:
            pad = self.launchpad.pads[pad_index]
            if pad.is_assigned:
                self._app._engine.load_sample(pad_index, pad)
            else:
                self._app._engine.unload_sample(pad_index)

    def stop_all(self) -> None:
        """Stop all playback."""
        if self._app and self._app._engine:
            self._app._engine.stop_all()
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

#### `LaunchpadEditor` - Orchestration
```python
class LaunchpadEditor(App):
    """Main TUI application (orchestrates services and UI)."""

    def __init__(self, config: AppConfig, set_name: Optional[str] = None):
        super().__init__()
        self.config = config
        self.set_name = set_name or "untitled"

        # Initialize launchpad
        self.launchpad = self._load_initial_launchpad()

        # Services (business logic)
        self.editor = EditorService(self.launchpad, config)
        self.preview = PreviewService(self.launchpad, config)

    def on_mount(self) -> None:
        """Start preview audio."""
        if self.preview.start():
            self.notify(f"Loaded {len(self.launchpad.assigned_pads)} samples")
        else:
            self.notify("Audio preview unavailable", severity="warning")

        # Select default pad
        self.editor.select_pad(0)
        self._update_ui_for_selection(0)

    def on_pad_grid_pad_selected(self, message: PadGrid.PadSelected) -> None:
        """Handle pad selection (coordination)."""
        pad_index = message.pad_index
        pad = self.editor.select_pad(pad_index)  # Business logic
        self._update_ui_for_selection(pad_index)  # UI update

    def action_browse_sample(self) -> None:
        """Open file browser."""
        def handle_file(file_path: Optional[Path]) -> None:
            if file_path and self.editor.selected_pad_index is not None:
                try:
                    # Business logic
                    pad = self.editor.assign_sample(
                        self.editor.selected_pad_index,
                        file_path
                    )

                    # Audio preview
                    self.preview.reload_pad(self.editor.selected_pad_index)

                    # UI update
                    self._update_ui_for_pad(self.editor.selected_pad_index, pad)

                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

        self.push_screen(FileBrowserScreen(self.config.samples_dir), handle_file)

    def _update_ui_for_selection(self, pad_index: int) -> None:
        """Update UI components after selection."""
        pad = self.launchpad.pads[pad_index]
        self.query_one(PadGrid).select_pad(pad_index)
        self.query_one(PadDetailsPanel).update_for_pad(pad_index, pad)

    def _update_ui_for_pad(self, pad_index: int, pad: Pad) -> None:
        """Update UI components after pad change."""
        self.query_one(PadGrid).update_pad(pad_index, pad)
        self.query_one(PadDetailsPanel).update_for_pad(pad_index, pad)
```

### 4. CLI Command (Thin Orchestrator)

```python
# cli/commands/edit.py
@click.command()
@click.option('--set', '-s', type=str, default=None)
@click.option('--samples-dir', type=click.Path(...), default=None)
def edit(set: Optional[str], samples_dir: Optional[Path]):
    """Edit sample sets with interactive TUI."""

    # Setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s',
        filename='launchsampler-edit.log'
    )

    # Load config
    config = AppConfig.load_or_default()
    if samples_dir:
        config.samples_dir = samples_dir

    # Run app (delegates to tui layer)
    from launchsampler.tui.app import LaunchpadEditor
    app = LaunchpadEditor(config, set_name=set)
    app.run()
```

---

## Benefits of This Restructure

### 1. ✅ Reuses Existing Architecture
- `PreviewService` wraps `SamplerApplication` (no duplication)
- Core layer handles audio lifecycle
- Models remain single source of truth

### 2. ✅ Clean Separation of Concerns
- **Services**: Business logic (editing, preview)
- **Widgets**: Pure presentation (display state)
- **App**: Orchestration (coordinate services ↔ UI)

### 3. ✅ Highly Reusable
- Widgets can be used in other TUI apps
- Services can be tested independently
- Screens are self-contained

### 4. ✅ Easier to Test
```python
# Test business logic without UI
def test_assign_sample():
    launchpad = Launchpad.create_empty()
    editor = EditorService(launchpad, config)

    pad = editor.assign_sample(0, Path("kick.wav"))

    assert pad.is_assigned
    assert pad.sample.name == "kick"
```

### 5. ✅ Better Maintainability
- Each file has ~100-200 lines (not 897)
- Clear component boundaries
- Easy to locate and modify features

### 6. ✅ Scalability
- Add new widgets easily (waveform display, volume slider)
- Add new services (undo/redo, batch operations)
- Extend screens without affecting core logic

---

## Migration Strategy

### Phase 1: Extract Services (No UI changes)
1. Create `tui/services/editor_service.py` and `preview_service.py`
2. Move business logic from `LaunchpadEditor` to services
3. `LaunchpadEditor` delegates to services
4. **Result**: Same UI, cleaner separation

### Phase 2: Extract Widgets
1. Move widgets to `tui/widgets/` (one file each)
2. Update imports in app
3. **Result**: Same functionality, better organization

### Phase 3: Extract Screens
1. Move screens to `tui/screens/` (one file each)
2. Extract shared styles to `styles/default.tcss`
3. **Result**: Reusable components

### Phase 4: Integrate PreviewService with SamplerApplication
1. Replace direct `SamplerEngine` usage with `SamplerApplication`
2. Remove duplicated audio setup code
3. **Result**: Consistent architecture across CLI commands

---

## Conclusion

The current `edit.py` is a **monolithic mess** that:
- Duplicates logic from the well-designed core layer
- Mixes presentation, business logic, and state management
- Is hard to test, maintain, and extend

The proposed restructure:
- **Respects** the existing architecture patterns
- **Reuses** `SamplerApplication` instead of reimplementing
- **Separates** concerns into services, widgets, and orchestration
- **Enables** testing, reusability, and future features

**This transforms `edit.py` from a 897-line monolith into a clean, maintainable, and extensible TUI application that integrates seamlessly with the existing architecture.**
