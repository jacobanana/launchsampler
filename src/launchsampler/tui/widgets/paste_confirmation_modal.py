"""Modal dialog for confirming paste operations."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class PasteConfirmationModal(ModalScreen[bool]):
    """
    Modal dialog asking user to confirm overwriting a pad on paste.

    User is presented with two options when pasting to an occupied pad:
    - Overwrite: Replace target sample with clipboard contents
    - Cancel: Abort the paste operation
    """

    DEFAULT_CSS = """
    PasteConfirmationModal {
        align: center middle;
    }

    #dialog {
        width: 60;
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

    #action-prompt {
        width: 100%;
        content-align: center middle;
        padding: 1 0;
        text-style: bold;
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

    def __init__(self, target_index: int, current_sample_name: str) -> None:
        """
        Initialize the modal.

        Args:
            target_index: Index of target pad
            current_sample_name: Name of sample currently in target pad
        """
        super().__init__()
        self.target_index = target_index
        self.current_sample_name = current_sample_name

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        with Vertical(id="dialog"):
            yield Label(f"Pad {self.target_index} already has a sample", id="question")
            yield Label(f'"{self.current_sample_name}"', id="details")
            yield Label("Overwrite with clipboard contents?", id="action-prompt")
            with Horizontal(id="button-container"):
                yield Button("Overwrite", variant="error", id="overwrite-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "overwrite-btn":
            self.dismiss(True)
        elif event.button.id == "cancel-btn":
            self.dismiss(False)
