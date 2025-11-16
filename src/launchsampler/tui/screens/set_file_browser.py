"""Set file browser screen for loading saved sets."""

import logging
from os import path
from pathlib import Path
from typing import TYPE_CHECKING

from textual.markup import escape

from .base_browser import BaseBrowserScreen

if TYPE_CHECKING:
    from launchsampler.services import SetManagerService

logger = logging.getLogger(__name__)


class SetFileBrowserScreen(BaseBrowserScreen):
    """
    Screen for browsing and selecting saved set files (.json).

    Displays a directory tree and allows selection of set files.
    Shows metadata about sets when available. User can navigate
    anywhere on the filesystem to find set files.
    """

    def __init__(self, set_manager: "SetManagerService", *args, **kwargs):
        """
        Initialize the set file browser.

        Args:
            set_manager: Service for loading sets
        """
        super().__init__(*args, **kwargs)
        self.set_manager = set_manager

    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if path is a valid set file.

        Args:
            path: Path to validate

        Returns:
            True if path is a valid Set file that can be loaded
        """
        if not (path.exists() and path.is_file() and path.suffix.lower() == '.json'):
            return False

        # Validate it's actually a Set file by trying to load it
        try:
            self.set_manager.open_set(path)
            return True
        except Exception:
            return False

    def _get_selection_value(self) -> Path:
        """
        Get the selected set file path.

        Returns:
            Selected set file path
        """
        return self.selected_path

    def _get_title(self) -> str:
        """
        Get the screen title.

        Returns:
            Title markup string
        """
        return "[b]Load Set[/b]"

    def _get_instructions(self) -> str:
        """
        Get the usage instructions.

        Returns:
            Instructions markup string
        """
        return (
            "[b]Tree Navigation:[/b] ↑↓: navigate | →: expand | ←: collapse/up | Enter: select\n"
            "[b]Path Input:[/b] Type/paste path above, then Tab or Enter to navigate\n"
            "[b]File Type:[/b] Select a .json set file"
        )

    def _show_invalid_selection_error(self, path: Path) -> None:
        """
        Show error for invalid set file selection.

        Args:
            path: Invalid path that was selected
        """
        if path.is_dir():
            self.notify("Please select a set file, not a directory", severity="warning")
        elif path.suffix.lower() != '.json':
            self.notify("Please select a .json set file", severity="error")
        else:
            self.notify(
                "Invalid set file - cannot load this file",
                severity="error"
            )

    def _on_tree_file_selected(self, event) -> None:
        """
        Handle file selection - show metadata if it's a set file.

        Args:
            event: File selected event
        """
        file_path = Path(event.path)
        logger.info(f"File selected: {file_path}")

        # Only auto-select if it's a valid set file
        if file_path.suffix.lower() == '.json':
            logger.info(f"Attempting to load JSON file: {file_path}")
            try:
                # Try to load metadata
                set_obj = self.set_manager.open_set(file_path)
                assigned_count = len(set_obj.launchpad.assigned_pads)
                created = set_obj.created_at.strftime("%Y-%m-%d %H:%M")

                # Update selected path
                self.selected_path = file_path
                logger.info(f"Successfully loaded set: {set_obj.name} from {file_path}")

                # Show metadata notification
                self.notify(
                    f"{set_obj.name}: {assigned_count} pads, created {created}",
                    timeout=3
                )

                # Auto-select valid set file
                self._confirm_selection()

            except Exception as e:
                # Invalid set file - escape filename to avoid markup errors
                logger.error(f"Failed to load set file {file_path}: {e}", exc_info=True)
                self.notify(f"Invalid set file: {escape(file_path.name)}", severity="error")
        else:
            logger.info(f"Not a JSON file: {file_path}")
            # Not a JSON file
            self._show_invalid_selection_error(file_path)
