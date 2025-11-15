"""Widget representing a single pad in the grid."""

from textual.widgets import Static
from textual.message import Message

from launchsampler.models import Pad


class PadWidget(Static):
    """
    Widget representing a single pad (presentation only).

    Displays pad index, sample name, and applies CSS classes based on
    playback mode. Posts messages when clicked, allowing parent
    containers to handle selection logic.
    """

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

    PadWidget.loop_toggle {
        background: magenta 20%;
        border: solid magenta;
    }

    PadWidget.empty {
        background: $surface 10%;
        border: solid $surface;
    }

    PadWidget.selected {
        border: double $warning;
    }

    PadWidget.midi_on {
        border: double $warning 100%;
    }

    PadWidget.active {
        background: $warning 60%;
    }
    """

    class Selected(Message):
        """Message posted when pad is clicked."""

        def __init__(self, pad_index: int):
            super().__init__()
            self.pad_index = pad_index

    def __init__(self, pad_index: int, pad: Pad) -> None:
        """
        Initialize pad widget.

        Args:
            pad_index: Index of this pad (0-63)
            pad: Pad model instance
        """
        super().__init__()
        self.pad_index = pad_index
        self._pad = pad
        self._is_playing = False
        self._midi_on = False
        self.update_display()

    def update(self, pad: Pad) -> None:
        """
        Update display with new pad state.

        Args:
            pad: New pad state
        """
        self._pad = pad
        self.update_display()

    def update_display(self) -> None:
        """Render current pad state."""
        # Clear mode classes
        self.remove_class("one_shot", "loop", "hold", "loop_toggle", "empty")

        if self._pad.is_assigned:
            # Show pad index and truncated sample name
            name = self._pad.sample.name[:6] if self._pad.sample else "???"
            super().update(f"[b]{self.pad_index}[/b]\n{name}")

            # Add mode class for styling
            self.add_class(self._pad.mode.value)
        else:
            # Empty pad
            super().update(f"[dim]{self.pad_index}[/dim]\n—")
            self.add_class("empty")

    def set_playing(self, is_playing: bool) -> None:
        """
        Set the playing state of this pad.

        Args:
            is_playing: Whether the pad is currently playing audio
        """
        if is_playing != self._is_playing:
            self._is_playing = is_playing
            if is_playing:
                self.add_class("active")
            else:
                self.remove_class("active")
            self.refresh()

    def set_midi_on(self, midi_on: bool) -> None:
        """
        Set the MIDI note on/off state of this pad.

        Args:
            midi_on: Whether a MIDI note on is currently held for this pad
        """
        if midi_on != self._midi_on:
            self._midi_on = midi_on
            if midi_on:
                self.add_class("midi_on")
            else:
                self.remove_class("midi_on")
            self.refresh()

    def on_click(self) -> None:
        """Handle click event - post message for parent to handle."""
        self.post_message(self.Selected(self.pad_index))
