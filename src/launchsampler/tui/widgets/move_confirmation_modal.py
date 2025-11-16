"""Modal dialog for confirming pad move operations."""

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import Label, Button
from textual.containers import Vertical, Horizontal


class MoveConfirmationModal(ModalScreen[str]):
    """
    Modal dialog asking user to choose between overwrite or swap.

    User is presented with two options when moving a sample to an occupied pad:
    - Overwrite: Replace target sample (source pad becomes empty)
    - Swap: Exchange samples between source and target pads
    """

    DEFAULT_CSS = """
    MoveConfirmationModal {
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

    def __init__(self, source_index: int, target_index: int, target_sample_name: str) -> None:
        """
        Initialize the modal.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            target_sample_name: Name of sample in target pad
        """
        super().__init__()
        self.source_index = source_index
        self.target_index = target_index
        self.target_sample_name = target_sample_name

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        with Vertical(id="dialog"):
            yield Label(
                f"Pad {self.target_index} already has a sample",
                id="question"
            )
            yield Label(
                f'"{self.target_sample_name}"',
                id="details"
            )
            yield Label(
                "Choose an action:",
                id="action-prompt"
            )
            with Horizontal(id="button-container"):
                yield Button("Swap", variant="success", id="swap-btn")
                yield Button("Overwrite", variant="error", id="overwrite-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "overwrite-btn":
            event.stop()
            self.dismiss("overwrite")
        elif event.button.id == "swap-btn":
            event.stop()
            self.dismiss("swap")
        elif event.button.id == "cancel-btn":
            event.stop()
            self.dismiss("cancel")
