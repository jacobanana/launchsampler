"""Grid widget containing 8x8 pad widgets."""

from textual.containers import Container
from textual.app import ComposeResult
from textual.message import Message

from launchsampler.models import Launchpad, Pad
from .pad_widget import PadWidget


class PadGrid(Container):
    """
    8x8 grid of pad widgets (layout container).

    Arranges 64 pad widgets in an 8x8 grid layout, matching the
    physical Launchpad layout. Handles pad selection visualization
    and forwards selection events to parent.
    """

    DEFAULT_CSS = """
    PadGrid {
        layout: grid;
        grid-size: 8 8;
        grid-gutter: 1;
        padding: 1;
        height: auto;
    }
    """

    class PadSelected(Message):
        """Message posted when any pad is selected."""

        def __init__(self, pad_index: int):
            super().__init__()
            self.pad_index = pad_index

    def __init__(self, launchpad: Launchpad) -> None:
        """
        Initialize pad grid.

        Args:
            launchpad: Launchpad model containing all pads
        """
        super().__init__()
        self.launchpad = launchpad
        # Map pad_index to widget
        self.pad_widgets: dict[int, PadWidget] = {}

    def compose(self) -> ComposeResult:
        """
        Create the grid of pads.

        Launchpad layout: (0,0) is bottom-left, (7,7) is top-right
        Grid layout: top-left to bottom-right
        So we flip vertically: iterate from row 7 down to row 0
        """
        # Iterate rows from 7 (top) to 0 (bottom)
        for y in range(7, -1, -1):
            # Iterate columns from 0 (left) to 7 (right)
            for x in range(8):
                # Calculate pad index: row * 8 + col
                i = y * 8 + x
                pad = self.launchpad.pads[i]
                widget = PadWidget(i, pad)

                # Store widget by pad_index
                self.pad_widgets[i] = widget
                yield widget

    def update_pad(self, pad_index: int, pad: Pad) -> None:
        """
        Update a specific pad's display.

        Args:
            pad_index: Index of pad to update (0-63)
            pad: New pad state
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

    def on_pad_widget_selected(self, message: PadWidget.Selected) -> None:
        """
        Handle pad selection from child widgets.

        Forwards the selection event up to parent container.
        """
        # Don't consume the message, let it bubble up
        message.stop()

        # Post our own message for parent
        self.post_message(self.PadSelected(message.pad_index))
