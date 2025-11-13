"""Details panel showing information and controls for selected pad."""

from typing import Optional

from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual.widgets import Label, Button

from launchsampler.models import Pad


class PadDetailsPanel(Vertical):
    """
    Panel showing details and controls for the selected pad.

    Displays pad information (index, sample, mode, volume) and provides
    buttons for editing. Can be set to edit or play mode to disable/enable
    controls appropriately.
    """

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

    PadDetailsPanel Button {
        margin-top: 1;
    }

    PadDetailsPanel .button-row {
        height: auto;
        margin-top: 0;
    }
    """

    def __init__(self) -> None:
        """Initialize details panel."""
        super().__init__()
        self.selected_pad_index: Optional[int] = None
        self._current_mode = "edit"  # edit or play

    def compose(self) -> ComposeResult:
        """Create the details panel widgets."""
        yield Label("No pad selected", id="pad-info")
        yield Label("", id="sample-info")

        with Horizontal(classes="button-row"):
            yield Button("Browse", id="browse-btn", variant="primary", disabled=True)
            yield Button("Clear", id="clear-btn", variant="default", disabled=True)

        with Horizontal(classes="button-row"):
            yield Button("ONE_SHOT", id="mode-oneshot", variant="default", disabled=True)
            yield Button("LOOP", id="mode-loop", variant="default", disabled=True)
            yield Button("HOLD", id="mode-hold", variant="default", disabled=True)

        with Horizontal(classes="button-row"):
            yield Button("Test Pad", id="test-btn", variant="success", disabled=True)
            yield Button("Stop Audio", id="stop-btn", variant="error", disabled=True)

    def update_for_pad(self, pad_index: int, pad: Pad) -> None:
        """
        Update the panel to show info for selected pad.

        Args:
            pad_index: Index of selected pad (0-63)
            pad: Pad model instance
        """
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

        # Update button states based on pad and mode
        self._update_button_states(pad)

    def set_mode(self, mode: str) -> None:
        """
        Set the mode (edit or play) for the panel.

        Args:
            mode: "edit" or "play"
        """
        self._current_mode = mode

        # Refresh button states if we have a selected pad
        if self.selected_pad_index is not None:
            # Get current pad to update buttons
            # Note: We'll need to get this from parent, but for now just update based on mode
            edit_enabled = (mode == "edit")

            self.query_one("#browse-btn", Button).disabled = not edit_enabled
            self.query_one("#clear-btn", Button).disabled = not edit_enabled
            self.query_one("#mode-oneshot", Button).disabled = not edit_enabled
            self.query_one("#mode-loop", Button).disabled = not edit_enabled
            self.query_one("#mode-hold", Button).disabled = not edit_enabled

    def _update_button_states(self, pad: Pad) -> None:
        """Update button states based on pad state and current mode."""
        edit_enabled = (self._current_mode == "edit")

        # Edit controls - only enabled in edit mode
        self.query_one("#browse-btn", Button).disabled = not edit_enabled
        self.query_one("#clear-btn", Button).disabled = not edit_enabled or not pad.is_assigned
        self.query_one("#mode-oneshot", Button).disabled = not edit_enabled
        self.query_one("#mode-loop", Button).disabled = not edit_enabled
        self.query_one("#mode-hold", Button).disabled = not edit_enabled

        # Test controls - available in both modes
        self.query_one("#test-btn", Button).disabled = not pad.is_assigned
        self.query_one("#stop-btn", Button).disabled = not pad.is_assigned

        # Highlight current mode button
        if pad.is_assigned:
            for mode in ["oneshot", "loop", "hold"]:
                btn = self.query_one(f"#mode-{mode}", Button)
                btn_mode = mode.upper() if mode != "oneshot" else "ONE_SHOT"

                if pad.mode.value == btn_mode.lower():
                    btn.variant = "success"
                else:
                    btn.variant = "default"
