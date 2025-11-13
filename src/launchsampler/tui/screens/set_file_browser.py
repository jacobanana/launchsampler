"""Set file browser screen for loading saved sets."""

from pathlib import Path

from launchsampler.models import Set

from .base_browser import BaseBrowserScreen


class SetFileBrowserScreen(BaseBrowserScreen):
    """
    Screen for browsing and selecting saved set files (.json).

    Displays a directory tree and allows selection of set files.
    Shows metadata about sets when available. User can navigate
    anywhere on the filesystem to find set files.
    """

    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if path is a valid set file.

        Args:
            path: Path to validate

        Returns:
            True if path is an existing .json file that can be loaded as a Set
        """
        if not path.exists() or not path.is_file():
            return False
        
        if path.suffix.lower() != '.json':
            return False
        
        # Try to load it to verify it's a valid set file
        try:
            Set.load_from_file(path)
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
        
        # Only auto-select if it's a valid set file
        if file_path.suffix.lower() == '.json':
            try:
                # Try to load metadata
                set_obj = Set.load_from_file(file_path)
                assigned_count = len(set_obj.launchpad.assigned_pads)
                created = set_obj.created_at.strftime("%Y-%m-%d %H:%M")
                
                # Update selected path
                self.selected_path = file_path
                
                # Show metadata notification
                self.notify(
                    f"{set_obj.name}: {assigned_count} pads, created {created}",
                    timeout=3
                )
                
                # Auto-select valid set file
                self._confirm_selection()
                
            except Exception as e:
                # Invalid set file
                self.notify(f"Cannot load set: {e}", severity="error")
        else:
            # Not a JSON file
            self._show_invalid_selection_error(file_path)
