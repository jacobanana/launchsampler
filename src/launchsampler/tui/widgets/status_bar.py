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
        self._audio_device = "No Audio"
        self._midi_device = "No MIDI"
        self._update_display()

    def update_state(
        self,
        mode: str,
        connected: bool,
        voices: int,
        audio_device: str = "Unknown",
        midi_device: str = "No Device",
    ) -> None:
        """
        Update all status information.

        Args:
            mode: Current mode ("edit" or "play")
            connected: Whether MIDI is connected
            voices: Number of active voices
            audio_device: Name of the audio device
            midi_device: Name of the MIDI device
        """
        self._mode = mode
        self._connected = connected
        self._voices = voices
        self._audio_device = audio_device
        self._midi_device = midi_device
        self._update_display()

    def _update_display(self) -> None:
        """Update the status bar display."""
        # Mode indicator
        if self._mode == "edit":
            mode_text = "✏ EDIT"
            self.remove_class("play_mode")
            self.add_class("edit_mode")
        else:
            mode_text = "▶ PLAY"
            self.remove_class("edit_mode")
            self.add_class("play_mode")

        # Audio device
        audio_text = f"🔊 {self._audio_device}"

        # MIDI device with connection status
        midi_text = f"🎹 {self._midi_device}" if self._connected else "🎹 No MIDI"

        # Voice count
        voice_text = f"♫ {self._voices}" if self._voices > 0 else ""

        # Compose status line
        parts = [mode_text, audio_text, midi_text]
        if voice_text:
            parts.append(voice_text)

        self.update(" | ".join(parts))
