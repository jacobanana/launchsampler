"""Grid widget containing 8x8 pad widgets."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message

from launchsampler.models import Launchpad, Pad

from .pad_widget import PadWidget


class PadGrid(Container):
    """
    8x8 grid of pad widgets (layout container).

    Arranges 64 pad widgets in an 8x8 grid layout, matching the
    physical Launchpad layout. Handles pad selection visualization
    and forwards selection events to parent.

    This widget is stateless - it doesn't store the launchpad model.
    Pad data is passed explicitly when needed (data-driven approach).
    """

    DEFAULT_CSS = """
    PadGrid {
        layout: grid;
        grid-size: 8 8;
        grid-gutter: 1;
        padding: 1;
        height: 100%;
    }
    """

    class PadSelected(Message):
        """Message posted when any pad is selected."""

        def __init__(self, pad_index: int):
            super().__init__()
            self.pad_index = pad_index

    def __init__(self) -> None:
        """Initialize empty pad grid."""
        super().__init__()
        # Map pad_index to widget
        self.pad_widgets: dict[int, PadWidget] = {}
        self._initialized = False

    def compose(self) -> ComposeResult:
        """
        Create empty grid structure.

        Actual pad widgets are created later via initialize_pads()
        after the launchpad data is available.
        """
        # Return empty - will be populated via initialize_pads()
        return []

    def initialize_pads(self, launchpad: Launchpad) -> None:
        """
        Initialize the grid with pad widgets from launchpad data.

        This is called after the widget is mounted and launchpad data
        is available.

        Args:
            launchpad: Launchpad model containing all pad data

        Launchpad layout: (0,0) is bottom-left, (7,7) is top-right
        Grid layout: top-left to bottom-right
        So we flip vertically: iterate from row 7 down to row 0
        """
        if self._initialized:
            # Clear existing widgets
            for widget in self.pad_widgets.values():
                widget.remove()
            self.pad_widgets.clear()

        # Iterate rows from 7 (top) to 0 (bottom)
        for y in range(7, -1, -1):
            # Iterate columns from 0 (left) to 7 (right)
            for x in range(8):
                # Calculate pad index: row * 8 + col
                i = y * 8 + x
                pad = launchpad.pads[i]
                widget = PadWidget(i, pad)

                # Store widget by pad_index
                self.pad_widgets[i] = widget
                self.mount(widget)

        self._initialized = True

    def update_pad(self, pad_index: int, pad: Pad) -> None:
        """
        Update a specific pad's display.

        Args:
            pad_index: Index of pad to update (0-63)
            pad: New pad state (explicitly passed)
        """
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].update(pad)

    def select_pad(self, pad_index: int) -> None:
        """
        Visually mark a pad as selected.

        Args:
            pad_index: Index of pad to select (0-63)
        """
        # Deselect all pads
        for widget in self.pad_widgets.values():
            widget.remove_class("selected")

        # Select target pad
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].add_class("selected")

    def clear_selection(self) -> None:
        """Clear selection from all pads."""
        for widget in self.pad_widgets.values():
            widget.remove_class("selected")

    def set_pad_playing(self, pad_index: int, is_playing: bool) -> None:
        """
        Set the playing state of a pad.

        Args:
            pad_index: Index of pad (0-63)
            is_playing: Whether the pad is currently playing
        """
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].set_playing(is_playing)

    def set_pad_midi_on(self, pad_index: int, midi_on: bool) -> None:
        """
        Set the MIDI note on/off state of a pad.

        Args:
            pad_index: Index of pad (0-63)
            midi_on: Whether a MIDI note on is held for this pad
        """
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].set_midi_on(midi_on)

    def set_pad_unavailable(self, pad_index: int, is_unavailable: bool) -> None:
        """
        Set the unavailable state of a pad (sample file not found).

        Args:
            pad_index: Index of pad (0-63)
            is_unavailable: Whether the pad's sample file is unavailable
        """
        if pad_index in self.pad_widgets:
            self.pad_widgets[pad_index].set_unavailable(is_unavailable)

    def on_pad_widget_selected(self, message: PadWidget.Selected) -> None:
        """
        Handle pad selection from child widgets.

        Forwards the selection event up to parent container.
        """
        # Don't consume the message, let it bubble up
        message.stop()

        # Post our own message for parent
        self.post_message(self.PadSelected(message.pad_index))
