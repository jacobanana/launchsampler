"""File browser screen for selecting audio samples."""

from pathlib import Path

from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, DirectoryTree
from textual.binding import Binding


class FileBrowserScreen(Screen):
    """
    Screen for browsing and selecting audio sample files.

    Displays a directory tree and allows selection of audio files
    (.wav, .mp3, .flac, .ogg, .aiff). Automatically selects and
    dismisses when an audio file is chosen.
    """

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
        """
        Initialize file browser.

        Args:
            samples_dir: Directory to browse for samples
        """
        super().__init__()
        self.samples_dir = samples_dir

    def compose(self) -> ComposeResult:
        """Create the file browser layout."""
        with Vertical():
            yield Label(
                "[b]Select Sample File[/b]\n"
                "Navigate with arrow keys, press Enter to select",
                id="title"
            )
            yield DirectoryTree(str(self.samples_dir), id="tree")
            yield Label(
                "Select an audio file (.wav, .mp3, .flac, .ogg, .aiff)",
                id="info-panel"
            )
            with Horizontal():
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """
        Handle file selection in the tree.

        Automatically selects and dismisses with the file if it's an
        audio file. Shows error for non-audio files.
        """
        file_path = Path(event.path)

        # Check if it's an audio file
        if file_path.suffix.lower() in ['.wav', '.mp3', '.flac', '.ogg', '.aiff']:
            # Automatically select and dismiss with the file
            self.dismiss(file_path)
        else:
            # Show error for non-audio files
            info_panel = self.query_one("#info-panel", Label)
            info_panel.update(
                "[red]Not an audio file - please select .wav, .mp3, "
                ".flac, .ogg, or .aiff[/red]"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)
