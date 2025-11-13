"""Save set screen for naming and saving configurations."""

from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Input
from textual.binding import Binding


class SaveSetScreen(Screen):
    """
    Screen for saving a set with a name.

    Prompts user to enter a name for the current configuration
    and saves it to the sets directory.
    """

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
        """
        Initialize save set screen.

        Args:
            current_name: Current name of the set (default value)
        """
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
            yield Label(
                "[dim]Set will be saved to: config/sets/[/dim]",
                id="hint"
            )
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
