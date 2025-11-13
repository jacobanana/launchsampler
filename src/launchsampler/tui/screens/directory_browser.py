"""Directory browser screen for loading samples from a folder."""

from pathlib import Path

from .base_browser import BaseBrowserScreen


class DirectoryBrowserScreen(BaseBrowserScreen):
    """
    Screen for browsing and selecting directories containing samples.

    Displays a directory tree and allows selection of directories.
    User can select a directory by pressing Enter on it or using
    the "Select" button.
    """

    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if path is a valid directory.

        Args:
            path: Path to validate

        Returns:
            True if path is an existing directory
        """
        return path.exists() and path.is_dir()

    def _get_selection_value(self) -> Path:
        """
        Get the selected directory path.

        Returns:
            Selected directory path
        """
        return self.selected_path

    def _get_title(self) -> str:
        """
        Get the screen title.

        Returns:
            Title markup string
        """
        return "[b]Open Directory[/b]"

    def _get_instructions(self) -> str:
        """
        Get the usage instructions.

        Returns:
            Instructions markup string
        """
        return (
            "[b]Tree Navigation:[/b] ↑↓: navigate | →: expand | ←: collapse/up | Enter: select\n"
            "[b]Path Input:[/b] Type/paste path above, then Tab or Enter to navigate"
        )
