"""File browser screen for selecting audio samples."""

from pathlib import Path

from .base_browser import BaseBrowserScreen


class FileBrowserScreen(BaseBrowserScreen):
    """
    Screen for browsing and selecting audio sample files.

    Displays a directory tree and allows selection of audio files
    (.wav, .mp3, .flac, .ogg, .aiff). Automatically selects and
    dismisses when an audio file is chosen.
    """

    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.aiff'}

    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if path is a valid audio file.

        Args:
            path: Path to validate

        Returns:
            True if path is an existing audio file
        """
        return (
            path.exists() 
            and path.is_file() 
            and path.suffix.lower() in self.AUDIO_EXTENSIONS
        )

    def _get_selection_value(self) -> Path:
        """
        Get the selected file path.

        Returns:
            Selected file path
        """
        return self.selected_path

    def _get_title(self) -> str:
        """
        Get the screen title.

        Returns:
            Title markup string
        """
        return "[b]Select Sample File[/b]"

    def _get_instructions(self) -> str:
        """
        Get the usage instructions.

        Returns:
            Instructions markup string
        """
        return (
            "[b]Tree Navigation:[/b] ↑↓: navigate | →: expand | ←: collapse/up | Enter: select\n"
            "[b]Path Input:[/b] Type/paste path above, then Tab or Enter to navigate\n"
            "[b]File Types:[/b] .wav, .mp3, .flac, .ogg, .aiff"
        )

    def _show_invalid_selection_error(self, path: Path) -> None:
        """
        Show error for invalid file selection.

        Args:
            path: Invalid path that was selected
        """
        if path.is_dir():
            self.notify("Please select a file, not a directory", severity="warning")
        else:
            self.notify(
                f"Not an audio file - please select .wav, .mp3, .flac, .ogg, or .aiff",
                severity="error"
            )
