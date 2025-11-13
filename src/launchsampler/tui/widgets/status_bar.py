"""Status bar widget showing mode, MIDI status, and active voices."""

from textual.widgets import Static


class StatusBar(Static):
    """
    Status bar displaying current application state.

    Shows:
    - Current mode (Edit or Play)
    - MIDI connection status
    - Active voice count
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
        dock: bottom;
    }

    StatusBar.edit_mode {
        background: $accent;
    }

    StatusBar.play_mode {
        background: $success;
    }
    """

    def __init__(self) -> None:
        """Initialize status bar."""
        super().__init__()
        self._mode = "edit"
        self._connected = False
        self._voices = 0
        self._update_display()

    def update_state(self, mode: str, connected: bool, voices: int) -> None:
        """
        Update all status information.

        Args:
            mode: Current mode ("edit" or "play")
            connected: Whether MIDI is connected
            voices: Number of active voices
        """
        self._mode = mode
        self._connected = connected
        self._voices = voices
        self._update_display()

    def _update_display(self) -> None:
        """Update the status bar display."""
        # Mode indicator
        if self._mode == "edit":
            mode_text = "✏ EDIT MODE"
            self.remove_class("play_mode")
            self.add_class("edit_mode")
        else:
            mode_text = "▶ PLAY MODE"
            self.remove_class("edit_mode")
            self.add_class("play_mode")

        # MIDI status
        if self._mode == "play":
            midi_text = "● MIDI Connected" if self._connected else "○ MIDI Disconnected"
        else:
            midi_text = "MIDI: Off"

        # Voice count
        voice_text = f"♫ {self._voices} voices" if self._voices > 0 else ""

        # Compose status line
        parts = [mode_text, midi_text]
        if voice_text:
            parts.append(voice_text)

        self.update(" | ".join(parts))
