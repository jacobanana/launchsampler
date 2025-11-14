"""Details panel showing information and controls for selected pad."""

from typing import Optional

from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual.widgets import Label, Button, Input
from textual.message import Message

from launchsampler.models import Pad


class NoTabInput(Input):
    """Input that doesn't move focus to next field on Enter."""

    def __init__(self, *args, **kwargs):
        """Initialize with submit tracking."""
        super().__init__(*args, **kwargs)
        self._just_submitted = False

    def action_submit(self) -> None:
        """Override submit action to prevent focus moving to next field."""
        # Run validators and post submitted message
        self.validate(self.value)
        self.post_message(self.Submitted(self, self.value))
        # Set flag to prevent duplicate submission on blur
        self._just_submitted = True
        # Focus the grandparent (PadDetailsPanel) to remove focus from input
        # Structure: PadDetailsPanel > Horizontal > NoTabInput
        if self.parent and self.parent.parent:
            self.parent.parent.focus()

    def _on_blur(self, event) -> None:
        """Submit when losing focus (e.g., via Tab)."""
        # Don't submit again if we just submitted via action_submit
        if self._just_submitted:
            self._just_submitted = False
            super()._on_blur(event)
            return

        # Validate and submit when blurring
        self.validate(self.value)
        self.post_message(self.Submitted(self, self.value))
        # Call parent handler
        super()._on_blur(event)


class PadDetailsPanel(Vertical, can_focus=True):
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

    PadDetailsPanel .input-container {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    PadDetailsPanel #name-input {
        height: 3;
        padding: 0 1;
        margin: 0;
    }

    PadDetailsPanel .volume-container {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    PadDetailsPanel #volume-input {
        width: 15;
        height: 3;
        padding: 0 1;
        margin: 0;
    }

    PadDetailsPanel .move-container {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    PadDetailsPanel #move-input {
        width: 15;
        height: 3;
        padding: 0 1;
        margin: 0;
    }
    """

    class VolumeChanged(Message):
        """Message sent when volume is changed."""

        def __init__(self, pad_index: int, volume: float) -> None:
            """
            Initialize message.

            Args:
                pad_index: Index of pad (0-63)
                volume: New volume (0.0 - 1.0)
            """
            super().__init__()
            self.pad_index = pad_index
            self.volume = volume

    class NameChanged(Message):
        """Message sent when sample name is changed."""

        def __init__(self, pad_index: int, name: str) -> None:
            """
            Initialize message.

            Args:
                pad_index: Index of pad (0-63)
                name: New sample name
            """
            super().__init__()
            self.pad_index = pad_index
            self.name = name

    class MovePadRequested(Message):
        """Message sent when user requests to move pad to another location."""

        def __init__(self, source_index: int, target_index: int) -> None:
            """
            Initialize message.

            Args:
                source_index: Index of source pad (0-63)
                target_index: Index of target pad (0-63)
            """
            super().__init__()
            self.source_index = source_index
            self.target_index = target_index

    def __init__(self) -> None:
        """Initialize details panel."""
        super().__init__()
        self.selected_pad_index: Optional[int] = None
        self._current_mode = "edit"  # edit or play

    def compose(self) -> ComposeResult:
        """Create the details panel widgets."""
        yield Label("No pad selected", id="pad-info")
        yield Label("", id="sample-info")

        with Horizontal(classes="input-container"):
            yield Label("Name:", shrink=True)
            yield NoTabInput(placeholder="Sample name", id="name-input", disabled=True)

        with Horizontal(classes="volume-container"):
            yield Label("Volume:", shrink=True)
            yield NoTabInput(placeholder="0-100", id="volume-input", disabled=True)
            yield Label("%", shrink=True)

        with Horizontal(classes="move-container"):
            yield Label("Move to:", shrink=True)
            yield NoTabInput(placeholder="0-63", id="move-input", disabled=True)

        with Horizontal(classes="button-row"):
            yield Button("Browse", id="browse-btn", variant="primary", disabled=True)
            yield Button("Clear", id="clear-btn", variant="default", disabled=True)

        with Horizontal(classes="button-row"):
            yield Button("ONE_SHOT", id="mode-oneshot", variant="default", disabled=True)
            yield Button("LOOP", id="mode-loop", variant="default", disabled=True)

        with Horizontal(classes="button-row"):
            yield Button("HOLD", id="mode-hold", variant="default", disabled=True)
            yield Button("LOOP_TOGGLE", id="mode-looptoggle", variant="default", disabled=True)

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
                f"Path: {pad.sample.path}\n"
                f"Mode: {pad.mode.value}"
            )
        else:
            sample_info.update("[dim]No sample assigned[/dim]")

        # Update name input
        name_input = self.query_one("#name-input", Input)
        if pad.is_assigned and pad.sample:
            name_input.value = pad.sample.name
        else:
            name_input.value = ""

        # Update volume input
        volume_input = self.query_one("#volume-input", Input)
        if pad.is_assigned:
            volume_input.value = str(int(pad.volume * 100))
        else:
            volume_input.value = ""

        # Clear move input
        move_input = self.query_one("#move-input", Input)
        move_input.value = ""

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

            self.query_one("#name-input", Input).disabled = not edit_enabled
            self.query_one("#volume-input", Input).disabled = not edit_enabled
            self.query_one("#move-input", Input).disabled = not edit_enabled
            self.query_one("#browse-btn", Button).disabled = not edit_enabled
            self.query_one("#clear-btn", Button).disabled = not edit_enabled
            self.query_one("#mode-oneshot", Button).disabled = not edit_enabled
            self.query_one("#mode-loop", Button).disabled = not edit_enabled
            self.query_one("#mode-hold", Button).disabled = not edit_enabled
            self.query_one("#mode-looptoggle", Button).disabled = not edit_enabled

    def _update_button_states(self, pad: Pad) -> None:
        """Update button states based on pad state and current mode."""
        edit_enabled = (self._current_mode == "edit")

        # Name input - only enabled in edit mode and if pad has sample
        name_input = self.query_one("#name-input", Input)
        name_input.disabled = not (edit_enabled and pad.is_assigned)

        # Volume input - only enabled in edit mode and if pad has sample
        volume_input = self.query_one("#volume-input", Input)
        volume_input.disabled = not (edit_enabled and pad.is_assigned)

        # Move input - only enabled in edit mode and if pad has sample
        move_input = self.query_one("#move-input", Input)
        move_input.disabled = not (edit_enabled and pad.is_assigned)

        # Edit controls - only enabled in edit mode
        self.query_one("#browse-btn", Button).disabled = not edit_enabled
        self.query_one("#clear-btn", Button).disabled = not edit_enabled or not pad.is_assigned
        self.query_one("#mode-oneshot", Button).disabled = not edit_enabled
        self.query_one("#mode-loop", Button).disabled = not edit_enabled
        self.query_one("#mode-hold", Button).disabled = not edit_enabled
        self.query_one("#mode-looptoggle", Button).disabled = not edit_enabled

        # Test controls - available in both modes
        self.query_one("#test-btn", Button).disabled = not pad.is_assigned
        self.query_one("#stop-btn", Button).disabled = not pad.is_assigned

        # Highlight current mode button
        if pad.is_assigned:
            for mode in ["oneshot", "loop", "hold", "looptoggle"]:
                btn = self.query_one(f"#mode-{mode}", Button)
                btn_mode = mode.upper() if mode not in ["oneshot", "looptoggle"] else ("ONE_SHOT" if mode == "oneshot" else "LOOP_TOGGLE")

                if pad.mode.value == btn_mode.lower():
                    btn.variant = "success"
                else:
                    btn.variant = "default"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submissions."""
        if self.selected_pad_index is None:
            return

        if event.input.id == "name-input":
            # Update sample name
            name = event.value.strip()
            if name:  # Only update if not empty
                self.post_message(self.NameChanged(self.selected_pad_index, name))

        elif event.input.id == "volume-input":
            try:
                # Parse volume as percentage (0-100)
                volume_percent = int(event.value)
                if 0 <= volume_percent <= 100:
                    volume = volume_percent / 100.0
                    # Post message for parent to handle
                    self.post_message(self.VolumeChanged(self.selected_pad_index, volume))
            except ValueError:
                # Invalid input, keep current value
                pass

        elif event.input.id == "move-input":
            try:
                # Parse target pad index (0-63)
                target_index = int(event.value)
                if 0 <= target_index <= 63:
                    # Post message for parent to handle
                    self.post_message(self.MovePadRequested(self.selected_pad_index, target_index))
                    # Clear the input after submission
                    event.input.value = ""
                else:
                    # Out of range, clear it
                    event.input.value = ""
            except ValueError:
                # Invalid input, clear it
                event.input.value = ""
