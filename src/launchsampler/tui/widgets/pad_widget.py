"""Widget representing a single pad in the grid."""

from textual.widgets import Static
from textual.message import Message

from launchsampler.models import Pad
from launchsampler.ui_shared import MODE_COLORS, PLAYING_COLOR


def _generate_pad_css() -> str:
    """Generate CSS dynamically from centralized color scheme.

    CSS class names are automatically derived from PlaybackMode enum values.
    Colors come from the LaunchpadColor enum.
    """
    css_lines = [
        "PadWidget {",
        "    width: 100%;",
        "    height: 100%;",
        "    border: solid $primary;",
        "    content-align: center middle;",
        "}",
        "",
    ]

    # Generate mode-specific CSS from centralized colors
    # CSS class names are derived from mode.value (e.g., "one_shot", "loop")
    for mode, launchpad_color in MODE_COLORS.items():
        css_class = mode.value  # e.g., "one_shot", "loop", "hold", "loop_toggle"
        hex_color = launchpad_color.rgb.to_hex()
        css_lines.extend([
            f"PadWidget.{css_class} {{",
            f"    background: {hex_color} 20%;",
            f"    border: solid {hex_color};",
            "}",
            "",
        ])

    # Empty pad styling
    css_lines.extend([
        "PadWidget.empty {",
        "    background: $surface 10%;",
        "    border: solid $surface;",
        "}",
        "",
    ])

    # Selection styling (TUI only)
    css_lines.extend([
        "PadWidget.selected {",
        "    border: double $warning 80%;",
        "}",
        "",
    ])

    # MIDI on styling (TUI only)
    css_lines.extend([
        "PadWidget.midi_on {",
        "    border: double $primary 60%;",
        "}",
        "",
    ])

    # Playing/active state from centralized color
    playing_hex = PLAYING_COLOR.rgb.to_hex()
    css_lines.extend([
        "PadWidget.active {",
        f"    background: {playing_hex} 60%;",
        f"    border: solid {playing_hex};",
        "}",
        "",
    ])

    # Unavailable sample state (file not found)
    # Base state - show error border and background
    css_lines.extend([
        "PadWidget.unavailable {",
        "    background: $error 10%;",
        "    border: solid $error;",
        "}",
        "",
    ])

    # Unavailable + selected state - selection border takes priority over error border
    css_lines.extend([
        "PadWidget.unavailable.selected {",
        "    border: double $warning 80%;",
        "}",
        "",
    ])

    # Unavailable + active state - active border takes priority over error border
    css_lines.extend([
        f"PadWidget.unavailable.active {{",
        f"    border: solid {playing_hex};",
        "}",
        "",
    ])

    # Unavailable + midi_on state - midi border takes priority over error border
    css_lines.extend([
        "PadWidget.unavailable.midi_on {",
        "    border: double $primary 60%;",
        "}",
    ])

    return "\n".join(css_lines)


class PadWidget(Static):
    """
    Widget representing a single pad (presentation only).

    Displays pad index, sample name, and applies CSS classes based on
    playback mode. Posts messages when clicked, allowing parent
    containers to handle selection logic.
    """

    # Generate CSS dynamically from centralized color scheme
    DEFAULT_CSS = _generate_pad_css()

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
        self._is_unavailable = False
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
        # Clear mode classes (but preserve playing/midi state classes)
        self.remove_class("one_shot", "toggle", "hold", "loop", "loop_toggle", "empty")

        if self._pad.is_assigned:
            # Show pad index and sample name with warning if unavailable
            name = self._pad.sample.name if self._pad.sample else "???"

            # Prepend warning indicator to name if sample file is unavailable
            if self._is_unavailable:
                name = f"!! {name} !!"

            super().update(f"[b]{self.pad_index}[/b]\n{name}")

            # Add mode class for styling (from centralized colors)
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

    def set_unavailable(self, is_unavailable: bool) -> None:
        """
        Set the unavailable state of this pad (sample file not found).

        Args:
            is_unavailable: Whether the pad's sample file is unavailable
        """
        if is_unavailable != self._is_unavailable:
            self._is_unavailable = is_unavailable
            if is_unavailable:
                self.add_class("unavailable")
            else:
                self.remove_class("unavailable")
            self.update_display()

    def on_click(self) -> None:
        """Handle click event - post message for parent to handle."""
        self.post_message(self.Selected(self.pad_index))
