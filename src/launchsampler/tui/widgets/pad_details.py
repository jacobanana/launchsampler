"""Details panel showing information and controls for selected pad."""

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Rule

from launchsampler.audio.data import AudioData
from launchsampler.models import Pad


class NoTabInput(Input):
    """Input that doesn't move focus to next field on Enter."""

    DEFAULT_CSS = """
    NoTabInput {
        height: 1;
        max-height: 1;
        border: none;
        padding: 0;
        margin: 0;
    }

    NoTabInput:focus {
        border: none;
    }

    NoTabInput.-invalid {
        border: none;
        background: $error 20%;
    }

    NoTabInput.-invalid:focus {
        border: none;
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize with submit tracking."""
        super().__init__(*args, **kwargs)
        self._just_submitted = False

    async def action_submit(self) -> None:
        """Override submit action to prevent focus moving to next field."""
        # Run validators and post submitted message
        self.validate(self.value)
        self.post_message(self.Submitted(self, self.value))
        # Set flag to prevent duplicate submission on blur
        self._just_submitted = True
        # Focus the grandparent (PadDetailsPanel) to remove focus from input
        # Structure: PadDetailsPanel > Horizontal > NoTabInput
        # Type ignore: mypy doesn't recognize that parent.parent is a Widget at runtime
        if self.parent and self.parent.parent:
            self.parent.parent.focus()  # type: ignore[attr-defined]

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
        margin-bottom: 0;
    }

    PadDetailsPanel .pad-header {
        height: auto;
        layout: horizontal;
        margin-bottom: 1;
    }

    PadDetailsPanel .pad-header > Label:first-child {
        width: 50%;
    }

    PadDetailsPanel .pad-header > Label:last-child {
        width: 50%;
        text-align: right;
    }

    PadDetailsPanel #sample-info {
        margin: 0;
        padding: 0;
    }

    PadDetailsPanel .button-grid {
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
        margin-top: 1;
    }

    PadDetailsPanel .button-grid Button {
        width: 100%;
        content-align: center middle;
    }

    PadDetailsPanel .name-container {
        height: 1;
        margin: 1 0;
        layout: horizontal;
    }

    PadDetailsPanel .name-container > Label {
        width: 30%;
    }

    PadDetailsPanel .name-container > NoTabInput {
        width: 70%;
    }

    PadDetailsPanel #name-input {
        height: 1;
        padding: 0;
        margin: 0;
        padding: 0 1;
    }

    PadDetailsPanel .volume-container {
        height: 1;
        margin: 1 0;
        layout: horizontal;
    }

    PadDetailsPanel .volume-container > Label {
        width: 30%;
    }

    PadDetailsPanel .volume-container > NoTabInput {
        width: 70%;
    }

    PadDetailsPanel #volume-input {
        height: 1;
        margin: 0;
        padding: 0 1;
    }

    PadDetailsPanel .move-container {
        height: 1;
        margin: 1 0;
        layout: horizontal;
    }

    PadDetailsPanel .move-container > Label {
        width: 30%;
    }

    PadDetailsPanel .move-container > NoTabInput {
        width: 70%;
    }

    PadDetailsPanel #move-input {
        height: 1;
        padding: 0 1;
        margin: 0;
    }

    PadDetailsPanel #mode-radio {
        height: auto;
        margin: 0;
        padding: 0;
        border: none;
    }

    PadDetailsPanel RadioButton {
        margin: 0;
        padding: 0 1;
        height: 1;
        border: none;
    }

    PadDetailsPanel .control-buttons {
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
        dock: bottom;
    }

    PadDetailsPanel .control-buttons Button {
        width: 100%;
        content-align: center middle;
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
        self.selected_pad_index: int | None = None

    def compose(self) -> ComposeResult:
        """Create the details panel widgets."""
        with Horizontal(classes="pad-header"):
            yield Label("No pad selected", id="pad-info")
            yield Label("", id="pad-location")

        with Horizontal(classes="move-container"):
            yield Label("Move to:", shrink=True)
            yield NoTabInput(placeholder="0-63", id="move-input", disabled=True)

        yield Rule()

        with Horizontal(classes="name-container"):
            yield Label("Name:", shrink=True)
            yield NoTabInput(placeholder="Sample name", id="name-input", disabled=True)

        with Horizontal(classes="volume-container"):
            yield Label("Volume [%]:", shrink=True)
            yield NoTabInput(placeholder="0-100", id="volume-input", type="integer", disabled=True)

        with RadioSet(id="mode-radio"):
            yield RadioButton("\\[1] One Shot", id="mode-oneshot", disabled=True)
            yield RadioButton("\\[2] Toggle", id="mode-toggle", disabled=True)
            yield RadioButton("\\[3] Hold", id="mode-hold", disabled=True)
            yield RadioButton("\\[4] Loop", id="mode-loop", disabled=True)
            yield RadioButton("\\[5] Loop Toggle", id="mode-looptoggle", disabled=True)

        yield Rule()
        with Grid(classes="button-grid"):
            yield Button("[▪] Browse", id="browse-btn", variant="primary", disabled=True)
            yield Button("\\[X] Delete", id="clear-btn", variant="default", disabled=True)

        yield Rule()
        yield Label("", id="sample-info")  # gets updated by update_for_pad

        with Grid(classes="control-buttons"):
            yield Button("▶", id="test-btn", variant="success", disabled=True)
            yield Button("■", id="stop-btn", variant="error", disabled=True)

    def update_for_pad(self, pad_index: int, pad: Pad, audio_data: AudioData | None = None) -> None:
        """
        Update the panel to show info for selected pad.

        Args:
            pad_index: Index of selected pad (0-63)
            pad: Pad model instance
            audio_data: Optional AudioData object for the loaded sample
        """
        self.selected_pad_index = pad_index

        # Update pad info labels
        pad_info = self.query_one("#pad-info", Label)
        pad_info.update(f"[b]Pad {pad_index}[/b]")

        pad_location = self.query_one("#pad-location", Label)
        pad_location.update(f"[{pad_index % 8}, {pad_index // 8}]")

        # Update sample info
        sample_info = self.query_one("#sample-info", Label)
        if pad.is_assigned and pad.sample:
            # Build audio info string if audio data available
            audio_info_str = ""
            if audio_data is not None:
                audio_info_str = f"\nDuration: {audio_data.duration:.2f}s"
                audio_info_str += f"\nSample Rate: {audio_data.sample_rate} Hz"
                audio_info_str += f"\nChannels: {audio_data.num_channels}"

                # Add format info if available
                if audio_data.format:
                    audio_info_str += f"\nFormat: {audio_data.format}"
                    if audio_data.subtype:
                        audio_info_str += f" ({audio_data.subtype})"

                # Add file size
                info = audio_data.get_info()
                audio_info_str += f"\nSize: {info['size_str']}"
            else:
                audio_info_str = "\n[b]⚠️ File not found[/b]"

            sample_info.update(f"Path: {pad.sample.path}{audio_info_str}")
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

    def _update_button_states(self, pad: Pad) -> None:
        """
        Update button states based on pad state.

        The panel is only shown in edit mode, so all controls are always enabled
        based solely on whether a pad is assigned.
        """
        # Name, volume, and move inputs - only enabled if pad has sample
        self.query_one("#name-input", Input).disabled = not pad.is_assigned
        self.query_one("#volume-input", Input).disabled = not pad.is_assigned
        self.query_one("#move-input", Input).disabled = not pad.is_assigned

        # Browse button - always enabled (can assign to empty pads)
        self.query_one("#browse-btn", Button).disabled = False

        # Clear button and mode radio - only enabled if pad has sample
        self.query_one("#clear-btn", Button).disabled = not pad.is_assigned
        self.query_one("#mode-radio", RadioSet).disabled = not pad.is_assigned

        # Test/stop controls - only enabled if pad has sample
        self.query_one("#test-btn", Button).disabled = not pad.is_assigned
        self.query_one("#stop-btn", Button).disabled = not pad.is_assigned

        # Set the selected radio button based on current mode
        if pad.is_assigned:
            mode_map = {
                "one_shot": "mode-oneshot",
                "toggle": "mode-toggle",
                "hold": "mode-hold",
                "loop": "mode-loop",
                "loop_toggle": "mode-looptoggle",
            }
            radio_id = mode_map.get(pad.mode.value)
            if radio_id:
                radio_set = self.query_one("#mode-radio", RadioSet)
                # Find and press the correct radio button
                # Note: This will trigger RadioSet.Changed, but app.py checks
                # if mode actually changed before applying it
                try:
                    radio_button = radio_set.query_one(f"#{radio_id}", RadioButton)
                    radio_button.value = True
                except Exception:
                    pass

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
