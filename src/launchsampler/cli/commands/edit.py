"""Edit command - TUI for building and editing sample sets."""

import logging
from pathlib import Path
from typing import Optional

import click
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Header, Footer, Static, Label, Input, DirectoryTree, ListView, ListItem
from textual.binding import Binding
from textual.screen import Screen

from launchsampler.audio import AudioDevice
from launchsampler.core import SamplerEngine
from launchsampler.models import AppConfig, Launchpad, PlaybackMode, Pad, Sample, Set

logger = logging.getLogger(__name__)


class PadWidget(Static):
    """Widget representing a single pad in the grid."""
    
    DEFAULT_CSS = """
    PadWidget {
        width: 9;
        height: 4;
        border: solid $primary;
        content-align: center middle;
    }
    
    PadWidget.one_shot {
        background: $error 20%;
        border: solid $error;
    }
    
    PadWidget.loop {
        background: $success 20%;
        border: solid $success;
    }
    
    PadWidget.hold {
        background: $accent 20%;
        border: solid $accent;
    }
    
    PadWidget.empty {
        background: $surface 10%;
        border: solid $surface;
    }
    
    PadWidget.selected {
        border: double $warning;
    }
    """
    
    def __init__(self, pad_index: int, pad: Pad) -> None:
        super().__init__()
        self.pad_index = pad_index
        self.pad = pad
        self.update_display()
    
    def update_display(self) -> None:
        """Update the pad display based on current state."""
        # Clear existing classes
        self.remove_class("one_shot", "loop", "hold", "empty")
        
        if self.pad.is_assigned:
            # Show first 6 chars of sample name
            name = self.pad.sample.name[:6] if self.pad.sample else "???"
            self.update(f"[b]{self.pad_index}[/b]\n{name}")
            self.add_class(self.pad.mode.value)
        else:
            self.update(f"[dim]{self.pad_index}[/dim]\n—")
            self.add_class("empty")
    
    def on_click(self) -> None:
        """Handle pad click."""
        self.app.select_pad(self.pad_index)


class PadGrid(Container):
    """8x8 grid of pad widgets."""
    
    DEFAULT_CSS = """
    PadGrid {
        layout: grid;
        grid-size: 8 8;
        grid-gutter: 1;
        padding: 1;
        height: auto;
    }
    """
    
    def __init__(self, launchpad: Launchpad) -> None:
        super().__init__()
        self.launchpad = launchpad
        # Map pad_index to widget (not display order)
        self.pad_widgets: dict[int, PadWidget] = {}
    
    def compose(self) -> ComposeResult:
        """Create the grid of pads.
        
        Launchpad layout: (0,0) is bottom-left, (7,7) is top-right
        Grid layout: top-left to bottom-right
        So we need to flip vertically: start from row 7 down to row 0
        """
        # Iterate rows from 7 (top) to 0 (bottom)
        for y in range(7, -1, -1):
            # Iterate columns from 0 (left) to 7 (right)
            for x in range(8):
                # Calculate pad index: row * 8 + col
                i = y * 8 + x
                pad = self.launchpad.pads[i]
                widget = PadWidget(i, pad)
                # Store by pad_index, not display order
                self.pad_widgets[i] = widget
                yield widget
    
    def update_pad(self, pad_index: int) -> None:
        """Update a specific pad's display."""
        if pad_index in self.pad_widgets:
            # Update the widget's pad reference from the launchpad
            self.pad_widgets[pad_index].pad = self.launchpad.pads[pad_index]
            self.pad_widgets[pad_index].update_display()
    
    def select_pad(self, pad_index: int) -> None:
        """Visually mark a pad as selected."""
        # Deselect all
        for widget in self.pad_widgets.values():
            widget.remove_class("selected")
        
        # Select target
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].add_class("selected")


class PadDetailsPanel(Vertical):
    """Panel showing details of the selected pad."""
    
    DEFAULT_CSS = """
    PadDetailsPanel {
        width: 50;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }
    
    PadDetailsPanel Label {
        margin-bottom: 1;
    }
    
    PadDetailsPanel Input {
        margin-bottom: 1;
    }
    
    PadDetailsPanel Button {
        margin-top: 1;
    }
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.selected_pad_index: Optional[int] = None
    
    def compose(self) -> ComposeResult:
        """Create the details panel widgets."""
        yield Label("No pad selected", id="pad-info")
        yield Label("", id="sample-info")
        yield Horizontal(
            Button("Browse", id="browse-btn", variant="primary", disabled=True),
            Button("Clear", id="clear-btn", variant="default", disabled=True),
        )
        yield Horizontal(
            Button("ONE_SHOT", id="mode-oneshot", variant="default", disabled=True),
            Button("LOOP", id="mode-loop", variant="default", disabled=True),
            Button("HOLD", id="mode-hold", variant="default", disabled=True),
        )
        yield Horizontal(
            Button("Test Pad", id="test-btn", variant="success", disabled=True),
            Button("Stop Audio", id="stop-btn", variant="error", disabled=True),
        )
    
    def update_for_pad(self, pad_index: int, pad: Pad) -> None:
        """Update the panel to show info for selected pad."""
        self.selected_pad_index = pad_index
        
        # Update pad info label
        pad_info = self.query_one("#pad-info", Label)
        pad_info.update(f"[b]Pad {pad_index}[/b] ({pad_index // 8}, {pad_index % 8})")
        
        # Update sample info
        sample_info = self.query_one("#sample-info", Label)
        if pad.is_assigned and pad.sample:
            sample_info.update(
                f"Sample: [cyan]{pad.sample.name}[/cyan]\n"
                f"Path: {pad.sample.path}\n"
                f"Mode: {pad.mode.value}\n"
                f"Volume: {pad.volume:.0%}"
            )
        else:
            sample_info.update("[dim]No sample assigned[/dim]")
        
        # Enable controls
        self.query_one("#browse-btn", Button).disabled = False
        self.query_one("#clear-btn", Button).disabled = not pad.is_assigned
        self.query_one("#mode-oneshot", Button).disabled = False
        self.query_one("#mode-loop", Button).disabled = False
        self.query_one("#mode-hold", Button).disabled = False
        self.query_one("#test-btn", Button).disabled = not pad.is_assigned
        self.query_one("#stop-btn", Button).disabled = not pad.is_assigned
        
        # Highlight current mode
        for mode in ["oneshot", "loop", "hold"]:
            btn = self.query_one(f"#mode-{mode}", Button)
            btn_mode = mode.upper() if mode != "oneshot" else "ONE_SHOT"
            if pad.mode.value == btn_mode.lower():
                btn.variant = "success"
            else:
                btn.variant = "default"


class FileBrowserScreen(Screen):
    """Screen for browsing and selecting sample files."""
    
    DEFAULT_CSS = """
    FileBrowserScreen {
        align: center middle;
    }
    
    FileBrowserScreen > Vertical {
        width: 80;
        height: 40;
        background: $surface;
        border: thick $primary;
    }
    
    FileBrowserScreen DirectoryTree {
        height: 30;
        border: solid $primary;
        margin: 1;
    }
    
    FileBrowserScreen #info-panel {
        height: 5;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }
    
    FileBrowserScreen Horizontal {
        height: auto;
        align: center middle;
        margin: 1;
    }
    
    FileBrowserScreen Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, samples_dir: Path) -> None:
        super().__init__()
        self.samples_dir = samples_dir
    
    def compose(self) -> ComposeResult:
        """Create the file browser layout."""
        with Vertical():
            yield Label("[b]Select Sample File[/b]\nNavigate with arrow keys, press Enter to select", id="title")
            yield DirectoryTree(str(self.samples_dir), id="tree")
            yield Label("Select an audio file (.wav, .mp3, .flac, .ogg, .aiff)", id="info-panel")
            with Horizontal():
                yield Button("Cancel", id="cancel-btn", variant="default")
    
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the tree - automatically select audio files."""
        file_path = Path(event.path)
        
        # Check if it's an audio file
        if file_path.suffix.lower() in ['.wav', '.mp3', '.flac', '.ogg', '.aiff']:
            # Automatically select and dismiss with the file
            self.dismiss(file_path)
        else:
            # Show error for non-audio files
            info_panel = self.query_one("#info-panel", Label)
            info_panel.update("[red]Not an audio file - please select .wav, .mp3, .flac, .ogg, or .aiff[/red]")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)


class SaveSetScreen(Screen):
    """Screen for saving a set with a name."""
    
    DEFAULT_CSS = """
    SaveSetScreen {
        align: center middle;
    }
    
    SaveSetScreen > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2;
    }
    
    SaveSetScreen Label {
        margin-bottom: 1;
    }
    
    SaveSetScreen Input {
        margin-bottom: 2;
    }
    
    SaveSetScreen Horizontal {
        height: auto;
        align: center middle;
    }
    
    SaveSetScreen Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, current_name: str) -> None:
        super().__init__()
        self.current_name = current_name
    
    def compose(self) -> ComposeResult:
        """Create the save dialog layout."""
        with Vertical():
            yield Label("[b]Save Set[/b]")
            yield Label("Enter a name for this set:")
            yield Input(
                placeholder="my-drums",
                value=self.current_name if self.current_name != "untitled" else "",
                id="name-input"
            )
            yield Label("[dim]Set will be saved to: config/sets/[/dim]", id="hint")
            with Horizontal():
                yield Button("Save", id="save-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")
    
    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one(Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        name = event.value.strip()
        if name:
            self.dismiss(name)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-btn":
            name = self.query_one(Input).value.strip()
            if name:
                self.dismiss(name)
            else:
                self.query_one("#hint").update("[red]Please enter a name[/red]")
        elif event.button.id == "cancel-btn":
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)


class LoadSetScreen(Screen):
    """Screen for loading a saved set."""
    
    DEFAULT_CSS = """
    LoadSetScreen {
        align: center middle;
    }
    
    LoadSetScreen > Vertical {
        width: 60;
        height: 40;
        background: $surface;
        border: thick $primary;
        padding: 2;
    }
    
    LoadSetScreen Label {
        margin-bottom: 1;
    }
    
    LoadSetScreen ListView {
        height: 25;
        border: solid $primary;
        margin-bottom: 1;
    }
    
    LoadSetScreen Horizontal {
        height: auto;
        align: center middle;
    }
    
    LoadSetScreen Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "load_selected", "Load"),
    ]
    
    def __init__(self, sets_dir: Path) -> None:
        super().__init__()
        self.sets_dir = sets_dir
        self.set_files: list[Path] = []
    
    def compose(self) -> ComposeResult:
        """Create the load dialog layout."""
        with Vertical():
            yield Label("[b]Load Set[/b]")
            yield Label("Select a set to load:")
            yield ListView(id="sets-list")
            with Horizontal():
                yield Button("Load", id="load-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")
    
    def on_mount(self) -> None:
        """Populate the list when mounted."""
        list_view = self.query_one("#sets-list", ListView)
        
        # Find all .json files in sets directory
        if self.sets_dir.exists():
            self.set_files = sorted(self.sets_dir.glob("*.json"))
            
            if self.set_files:
                for set_file in self.set_files:
                    # Load set to get metadata
                    try:
                        set_obj = Set.load_from_file(set_file)
                        assigned_count = len(set_obj.launchpad.assigned_pads)
                        created = set_obj.created_at.strftime("%Y-%m-%d %H:%M")
                        list_view.append(
                            ListItem(
                                Label(f"[cyan]{set_obj.name}[/cyan] - {assigned_count} pads - {created}")
                            )
                        )
                    except Exception as e:
                        # Fallback if can't load set
                        list_view.append(
                            ListItem(Label(f"[dim]{set_file.stem}[/dim] (error loading)"))
                        )
            else:
                list_view.append(ListItem(Label("[dim]No saved sets found[/dim]")))
        else:
            list_view.append(ListItem(Label("[dim]No saved sets found[/dim]")))
    
    def action_load_selected(self) -> None:
        """Load the selected set."""
        list_view = self.query_one("#sets-list", ListView)
        if list_view.index is not None and list_view.index < len(self.set_files):
            self.dismiss(self.set_files[list_view.index])
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "load-btn":
            list_view = self.query_one("#sets-list", ListView)
            if list_view.index is not None and list_view.index < len(self.set_files):
                self.dismiss(self.set_files[list_view.index])
        elif event.button.id == "cancel-btn":
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)


class LaunchpadEditor(App):
    """TUI application for editing Launchpad sample sets."""
    
    TITLE = "Launchpad Sampler - Set Editor"
    SUB_TITLE = "Editing: untitled"
    CSS_PATH = None  # Using DEFAULT_CSS in widgets
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "save", "Save Set"),
        Binding("l", "load", "Load Set"),
        Binding("b", "browse_sample", "Browse"),
        Binding("c", "clear_pad", "Clear"),
        Binding("t", "test_selected", "Test Pad"),
        Binding("escape", "stop_audio", "Stop"),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("left", "navigate_left", "Left", show=False),
        Binding("right", "navigate_right", "Right", show=False),
    ]
    
    def __init__(self, config: AppConfig, set_name: Optional[str] = None):
        super().__init__()
        self.config = config
        self.set_name = set_name or "untitled"
        self.sub_title = f"Editing: {self.set_name}"
        self.launchpad: Optional[Launchpad] = None
        self.selected_pad_index: Optional[int] = None
        
        # Audio preview engine (not started by default)
        self.preview_engine: Optional[SamplerEngine] = None
        self.audio_device: Optional[AudioDevice] = None
    
    def compose(self) -> ComposeResult:
        """Create the main layout."""
        # Initialize launchpad before composing
        try:
            self.launchpad = Launchpad.from_sample_directory(
                samples_dir=self.config.samples_dir,
                auto_configure=True
            )
        except ValueError as e:
            logger.error(f"Error loading samples: {e}")
            self.launchpad = Launchpad.create_empty()
        
        yield Header(show_clock=True)
        
        with Horizontal():
            # Left side: Pad grid
            yield PadGrid(self.launchpad)
            
            # Right side: Details panel
            yield PadDetailsPanel()
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Notify about loaded samples
        if self.launchpad:
            self.notify(f"Loaded {len(self.launchpad.assigned_pads)} samples")
        
        # Initialize preview audio engine
        try:
            devices, _ = AudioDevice.list_output_devices()
            if devices:
                device_id = self.config.default_audio_device or devices[0][0]
                self.audio_device = AudioDevice(device=device_id, buffer_size=512)
                self.preview_engine = SamplerEngine(self.audio_device, num_pads=64)
                
                # Load all samples into engine
                for i, pad in enumerate(self.launchpad.pads):
                    if pad.is_assigned:
                        self.preview_engine.load_sample(i, pad)
                
                self.preview_engine.start()
                logger.info("Preview audio engine started")
        except Exception as e:
            logger.error(f"Failed to initialize audio preview: {e}")
            self.notify("Audio preview unavailable", severity="warning")
        
        # Select pad 0 (0,0) by default for immediate keyboard navigation
        self.select_pad(0)
    
    def select_pad(self, pad_index: int) -> None:
        """Select a pad and update the details panel."""
        self.selected_pad_index = pad_index
        
        # Update grid selection
        grid = self.query_one(PadGrid)
        grid.select_pad(pad_index)
        
        # Update details panel
        details = self.query_one(PadDetailsPanel)
        pad = self.launchpad.pads[pad_index]
        details.update_for_pad(pad_index, pad)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "test-btn":
            self.action_test_selected()
        elif button_id == "stop-btn":
            self.action_stop_audio()
        elif button_id == "clear-btn":
            self.clear_selected_pad()
        elif button_id.startswith("mode-"):
            mode_name = button_id.replace("mode-", "").upper()
            if mode_name == "ONESHOT":
                mode_name = "ONE_SHOT"
            self.set_pad_mode(PlaybackMode(mode_name.lower()))
        elif button_id == "browse-btn":
            self.action_browse_sample()
    
    def action_browse_sample(self) -> None:
        """Open file browser to assign a sample to the selected pad."""
        if self.selected_pad_index is None:
            self.notify("Please select a pad first", severity="warning")
            return
        
        def handle_file_selected(file_path: Optional[Path]) -> None:
            """Handle the result from the file browser."""
            if file_path:
                try:
                    # Create sample and assign to pad
                    sample = Sample.from_file(file_path)
                    pad = self.launchpad.pads[self.selected_pad_index]
                    pad.sample = sample
                    pad.volume = 0.8  # Default volume
                    
                    # Set default mode if not set
                    if not pad.is_assigned or pad.mode is None:
                        pad.mode = PlaybackMode.ONE_SHOT
                        pad.color = pad.mode.get_default_color()
                    
                    # Load into preview engine
                    if self.preview_engine:
                        self.preview_engine.load_sample(self.selected_pad_index, pad)
                    
                    # Update displays
                    grid = self.query_one(PadGrid)
                    grid.update_pad(self.selected_pad_index)
                    
                    details = self.query_one(PadDetailsPanel)
                    details.update_for_pad(self.selected_pad_index, pad)
                    
                except Exception as e:
                    self.notify(f"Error loading sample: {e}", severity="error")
        
        # Push the file browser screen
        self.push_screen(FileBrowserScreen(self.config.samples_dir), handle_file_selected)
    
    def action_test_selected(self) -> None:
        """Test the selected pad by playing its sample."""
        if self.selected_pad_index is not None and self.preview_engine:
            pad = self.launchpad.pads[self.selected_pad_index]
            if pad.is_assigned:
                # Trigger the pad (respects mode: ONE_SHOT, LOOP, HOLD)
                self.preview_engine.trigger_pad(self.selected_pad_index)
    
    def action_stop_audio(self) -> None:
        """Stop all audio playback."""
        if self.preview_engine:
            # Stop all playing samples
            self.preview_engine.stop_all()
            
            # For HOLD mode, also release the selected pad
            if self.selected_pad_index is not None:
                self.preview_engine.release_pad(self.selected_pad_index)
    
    def clear_selected_pad(self) -> None:
        """Clear the selected pad."""
        if self.selected_pad_index is not None:
            # Get the current pad position
            old_pad = self.launchpad.pads[self.selected_pad_index]
            
            # Replace with a fresh empty pad
            self.launchpad.pads[self.selected_pad_index] = Pad.empty(old_pad.x, old_pad.y)
            
            # Remove from preview engine if loaded
            if self.preview_engine:
                self.preview_engine.unload_sample(self.selected_pad_index)
            
            # Update displays
            grid = self.query_one(PadGrid)
            grid.update_pad(self.selected_pad_index)
            
            details = self.query_one(PadDetailsPanel)
            details.update_for_pad(self.selected_pad_index, self.launchpad.pads[self.selected_pad_index])
    
    def set_pad_mode(self, mode: PlaybackMode) -> None:
        """Set the playback mode for the selected pad."""
        if self.selected_pad_index is not None:
            pad = self.launchpad.pads[self.selected_pad_index]
            if pad.is_assigned:
                pad.mode = mode
                pad.color = mode.get_default_color()
                
                # Reload the sample into the preview engine to update the mode
                if self.preview_engine:
                    self.preview_engine.load_sample(self.selected_pad_index, pad)
                
                # Update displays
                grid = self.query_one(PadGrid)
                grid.update_pad(self.selected_pad_index)
                
                details = self.query_one(PadDetailsPanel)
                details.update_for_pad(self.selected_pad_index, pad)
    
    def action_navigate_up(self) -> None:
        """Navigate to the pad above the current selection."""
        if self.selected_pad_index is not None:
            # Calculate current x, y (remember: y=0 is bottom)
            x = self.selected_pad_index % 8
            y = self.selected_pad_index // 8
            
            # Move up (increase y, unless at top edge)
            if y < 7:
                new_index = (y + 1) * 8 + x
                self.select_pad(new_index)
    
    def action_navigate_down(self) -> None:
        """Navigate to the pad below the current selection."""
        if self.selected_pad_index is not None:
            # Calculate current x, y
            x = self.selected_pad_index % 8
            y = self.selected_pad_index // 8
            
            # Move down (decrease y, unless at bottom edge)
            if y > 0:
                new_index = (y - 1) * 8 + x
                self.select_pad(new_index)
    
    def action_navigate_left(self) -> None:
        """Navigate to the pad to the left of the current selection."""
        if self.selected_pad_index is not None:
            # Calculate current x, y
            x = self.selected_pad_index % 8
            y = self.selected_pad_index // 8
            
            # Move left (decrease x, unless at left edge)
            if x > 0:
                new_index = y * 8 + (x - 1)
                self.select_pad(new_index)
    
    def action_navigate_right(self) -> None:
        """Navigate to the pad to the right of the current selection."""
        if self.selected_pad_index is not None:
            # Calculate current x, y
            x = self.selected_pad_index % 8
            y = self.selected_pad_index // 8
            
            # Move right (increase x, unless at right edge)
            if x < 7:
                new_index = y * 8 + (x + 1)
                self.select_pad(new_index)
    
    def action_clear_pad(self) -> None:
        """Clear the selected pad (keyboard shortcut)."""
        if self.selected_pad_index is not None:
            self.clear_selected_pad()
    
    def action_save(self) -> None:
        """Save the current set."""
        def handle_save(name: Optional[str]) -> None:
            if name is None:
                return  # User cancelled
            
            try:
                # Ensure sets directory exists
                sets_dir = self.config.sets_dir
                sets_dir.mkdir(parents=True, exist_ok=True)
                
                # Create Set object
                set_obj = Set(
                    name=name,
                    launchpad=self.launchpad
                )
                
                # Save to file
                set_path = sets_dir / f"{name}.json"
                set_obj.save_to_file(set_path)
                
                # Update current set name
                self.set_name = name
                self.sub_title = f"Editing: {name}"
                
                self.notify(f"Saved set: {name}", severity="information")
            except Exception as e:
                self.notify(f"Error saving set: {e}", severity="error")
                logger.exception("Error saving set")
        
        # Show save dialog
        self.push_screen(SaveSetScreen(self.set_name), handle_save)
    
    def action_load(self) -> None:
        """Load a set."""
        def handle_load(set_path: Optional[Path]) -> None:
            if set_path is None:
                return  # User cancelled
            
            try:
                # Load the set
                set_obj = Set.load_from_file(set_path)
                
                # Update launchpad
                self.launchpad = set_obj.launchpad
                
                # Reload into preview engine
                if self.preview_engine:
                    for i, pad in enumerate(self.launchpad.pads):
                        if pad.is_assigned:
                            self.preview_engine.load_sample(i, pad)
                
                # Update grid
                grid = self.query_one(PadGrid)
                for i in range(64):
                    grid.update_pad(i)
                
                # Update selected pad details if one is selected
                if self.selected_pad_index is not None:
                    details = self.query_one(PadDetailsPanel)
                    details.update_pad(self.selected_pad_index, self.launchpad.pads[self.selected_pad_index])
                
                # Update current set name
                self.set_name = set_obj.name
                self.sub_title = f"Editing: {self.set_name}"
                
                self.notify(f"Loaded set: {set_obj.name}", severity="information")
            except Exception as e:
                self.notify(f"Error loading set: {e}", severity="error")
                logger.exception("Error loading set")
        
        # Show load dialog
        self.push_screen(LoadSetScreen(self.config.sets_dir), handle_load)
    
    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        if self.preview_engine:
            self.preview_engine.stop()
        if self.audio_device:
            self.audio_device.stop()


@click.command()
@click.option(
    '--set',
    '-s',
    type=str,
    default=None,
    help='Name of set to edit (creates new if doesn\'t exist)'
)
@click.option(
    '--samples-dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help='Directory containing samples (overrides config)'
)
def edit(set: Optional[str], samples_dir: Optional[Path]):
    """
    Edit sample sets with interactive TUI.
    
    Opens a terminal UI for building and editing Launchpad sample sets.
    Click on pads to select, assign samples, change modes, and test playback.
    
    Examples:
    
      # Edit a new set
      launchsampler edit --set my-drumkit
      
      # Edit with specific samples directory
      launchsampler edit --samples-dir ./samples
    """
    # Setup logging to file (not console, since we're in TUI mode)
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s',
        filename='launchsampler-edit.log'
    )
    
    # Load config
    config = AppConfig.load_or_default()
    
    if samples_dir:
        config.samples_dir = samples_dir
    
    # Run the TUI app
    app = LaunchpadEditor(config, set_name=set)
    app.run()
