"""Modal dialog for confirming pad clear operations."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ClearConfirmationModal(ModalScreen[bool]):
    """Modal dialog asking user to confirm clearing a pad."""

    DEFAULT_CSS = """
    ClearConfirmationModal {
        align: center middle;
    }

    #dialog {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #question {
        width: 100%;
        content-align: center middle;
        padding: 1 0;
        text-style: bold;
    }

    #details {
        width: 100%;
        content-align: center middle;
        padding: 1 0;
        color: $text-muted;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0;
    }

    #button-container Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def __init__(self, pad_index: int, sample_name: str) -> None:
        """
        Initialize the modal.

        Args:
            pad_index: Index of pad to clear
            sample_name: Name of sample to clear
        """
        super().__init__()
        self.pad_index = pad_index
        self.sample_name = sample_name

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        with Vertical(id="dialog"):
            yield Label(f"Delete pad {self.pad_index}?", id="question")
            yield Label(f'"{self.sample_name}"', id="details")
            with Horizontal(id="button-container"):
                yield Button("Delete", variant="error", id="clear-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clear-btn":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-btn":
            event.stop()
            self.dismiss(False)
