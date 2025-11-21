"""Save set browser screen for choosing save location and filename."""

from pathlib import Path

from textual.widget import Widget
from textual.widgets import Input, Label

from .base_browser import BaseBrowserScreen


class SaveSetBrowserScreen(BaseBrowserScreen):
    """
    Screen for selecting save location and entering filename for sets.

    Displays a directory tree to choose location, with an input field
    for entering the set name. Returns a tuple of (directory, filename).
    """

    def __init__(self, start_dir: Path, default_name: str = "untitled") -> None:
        """
        Initialize save set browser.

        Args:
            start_dir: Directory to start browsing from
            default_name: Default name for the set
        """
        super().__init__(start_dir)
        self.default_name = default_name

    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if path is a valid directory for saving.

        Args:
            path: Path to validate

        Returns:
            True if path is an existing directory
        """
        return path.exists() and path.is_dir()

    def _get_selection_value(self) -> tuple[Path, str]:
        """
        Get the save location and filename.

        Returns:
            Tuple of (directory path, filename without extension)
        """
        name_input = self.query_one("#name-input", Input)
        filename = name_input.value.strip()

        # Remove .json extension if user added it
        if filename.endswith(".json"):
            filename = filename[:-5]

        return (self.selected_path, filename)

    def _get_title(self) -> str:
        """
        Get the screen title.

        Returns:
            Title markup string
        """
        return "[b]Save Set[/b]"

    def _get_instructions(self) -> str:
        """
        Get the usage instructions.

        Returns:
            Instructions markup string
        """
        return (
            "[b]Tree Navigation:[/b] ↑↓: navigate | →: expand | ←: collapse/up\n"
            "[b]Path Input:[/b] Type/paste directory path, then Tab or Enter to navigate\n"
            "[b]Save:[/b] Choose directory above, enter filename below, then press Enter or Select"
        )

    def _get_extra_widgets(self) -> list[Widget]:
        """
        Add filename input field.

        Returns:
            List containing filename input and label
        """
        return [
            Label("[b]Set Name:[/b]"),
            Input(
                placeholder="my-drums",
                value=self.default_name if self.default_name != "untitled" else "",
                id="name-input",
            ),
        ]

    def _validate_selection(self) -> bool:
        """
        Validate that directory is valid and filename is not empty.

        Returns:
            True if valid, False otherwise
        """
        # Check directory is valid
        if not self._is_valid_selection(self.selected_path):
            return False

        # Check filename is not empty
        name_input = self.query_one("#name-input", Input)
        filename = name_input.value.strip()

        return filename

    def _show_invalid_selection_error(self, path: Path) -> None:
        """
        Show error for invalid selection.

        Args:
            path: Invalid path that was selected
        """
        name_input = self.query_one("#name-input", Input)
        filename = name_input.value.strip()

        if not filename:
            self.notify("Please enter a set name", severity="warning")
        elif not self._is_valid_selection(path):
            self.notify("Please select a valid directory", severity="error")
        else:
            self.notify(f"Invalid save location: {path}", severity="error")

    def on_mount(self) -> None:
        """Focus the filename input when mounted."""
        # Give focus to the name input after a brief delay
        # (need to wait for tree to be mounted first)
        self.set_timer(0.1, self._focus_name_input)

    def _focus_name_input(self) -> None:
        """Focus the name input field."""
        try:
            name_input = self.query_one("#name-input", Input)
            name_input.focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "name-input":
            # Name input submitted - try to save
            self._confirm_selection()
        elif event.input.id == "path-input":
            # Path input submitted - navigate
            self._navigate_to_path(event.value)
