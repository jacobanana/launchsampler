"""Abstract base class for file/directory browser screens."""

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message_pump import _MessagePumpMeta
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Label


# Combine Screen's metaclass with ABCMeta to resolve metaclass conflict
class _BrowserScreenMeta(_MessagePumpMeta, ABCMeta):
    """Metaclass that combines Textual's Screen metaclass with ABC's metaclass."""

    pass


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that filters out hidden files and directories."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """
        Filter out hidden files and directories (those starting with a dot).

        Args:
            paths: Iterable of Path objects to filter

        Returns:
            Filtered iterable of Path objects
        """
        return [path for path in paths if not path.name.startswith(".")]


class BaseBrowserScreen(Screen, metaclass=_BrowserScreenMeta):
    """
    Abstract base class for all file/directory browser screens.

    Provides common functionality for navigating directories, path input,
    keyboard shortcuts, and consistent styling. Subclasses implement
    specific selection logic and validation.

    Subclasses must implement:
    - _is_valid_selection(path): Validate if a path can be selected
    - _get_selection_value(): Get the value to return on dismiss
    - _get_title(): Return the screen title
    - _get_instructions(): Return usage instructions
    """

    # Make this a modal screen to prevent parent app shortcuts from interfering
    MODAL = True

    DEFAULT_CSS = """
    BaseBrowserScreen {
        align: center middle;
    }

    BaseBrowserScreen > Vertical {
        width: 100;
        height: 45;
        background: $surface;
        border: thick $primary;
    }

    BaseBrowserScreen #title {
        height: auto;
        margin: 1;
        text-align: center;
    }

    BaseBrowserScreen #instructions {
        height: auto;
        width: 100%;
        background: $boost;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    BaseBrowserScreen DirectoryTree {
        height: 25;
        border: solid $primary;
        margin: 1;
    }

    BaseBrowserScreen #path-input {
        height: 3;
        border: solid $primary;
        margin: 1;
    }

    BaseBrowserScreen #button-row {
        height: 3;
        align: center middle;
        margin: 1;
    }

    BaseBrowserScreen Button {
        margin: 0 1;
    }

    BaseBrowserScreen #extra-widgets {
        height: auto;
        margin: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "select_current", "Select", priority=True),
        # Disable parent app's shortcuts by binding them to nothing
        Binding("e", "ignore", show=False, priority=True),
        Binding("p", "ignore", show=False, priority=True),
        Binding("s", "ignore", show=False, priority=True),
        Binding("l", "ignore", show=False, priority=True),
        Binding("o", "ignore", show=False, priority=True),
        Binding("b", "ignore", show=False, priority=True),
        Binding("c", "ignore", show=False, priority=True),
        Binding("t", "ignore", show=False, priority=True),
        Binding("q", "ignore", show=False, priority=True),
    ]

    def action_ignore(self) -> None:
        """No-op action to disable parent bindings."""
        pass

    def __init__(self, start_dir: Path) -> None:
        """
        Initialize browser.

        Args:
            start_dir: Directory to start browsing from
        """
        super().__init__()
        self.start_dir = start_dir
        self.selected_path: Path = start_dir

    # =================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =================================================================

    @abstractmethod
    def _is_valid_selection(self, path: Path) -> bool:
        """
        Check if a path is valid for selection.

        Args:
            path: Path to validate

        Returns:
            True if path can be selected, False otherwise
        """
        pass

    @abstractmethod
    def _get_selection_value(self) -> Any:
        """
        Get the value to return when selection is confirmed.

        Returns:
            Value to pass to dismiss() - could be Path, tuple, etc.
        """
        pass

    @abstractmethod
    def _get_title(self) -> str:
        """
        Get the title text for the browser.

        Returns:
            Title markup string
        """
        pass

    @abstractmethod
    def _get_instructions(self) -> str:
        """
        Get the instructions text for the browser.

        Returns:
            Instructions markup string
        """
        pass

    # =================================================================
    # Optional Hooks - Can be overridden by subclasses
    # =================================================================

    def _get_extra_widgets(self) -> list[Widget]:
        """
        Get additional widgets to include in the layout.

        These will be inserted between the path input and instructions.
        Override to add custom widgets (e.g., filename input for save dialog).

        Returns:
            List of additional widgets
        """
        return []

    def _get_buttons(self) -> list[Button]:
        """
        Get the buttons to display.

        Override to customize buttons.

        Returns:
            List of button widgets
        """
        return [
            Button("Select", id="select-btn", variant="primary"),
            Button("Cancel", id="cancel-btn", variant="default"),
        ]

    def _on_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """
        Handle directory node selection in tree.

        Override to customize behavior. Default updates selected_path and path input.

        Args:
            event: Directory selected event
        """
        self.selected_path = Path(event.path)
        path_input = self.query_one("#path-input", Input)
        path_input.value = str(self.selected_path)

    def _on_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """
        Handle file node selection in tree.

        Override to customize behavior. Default validates and dismisses.

        Args:
            event: File selected event
        """
        file_path = Path(event.path)
        if self._is_valid_selection(file_path):
            self.selected_path = file_path
            self._confirm_selection()
        else:
            self._show_invalid_selection_error(file_path)

    def _show_invalid_selection_error(self, path: Path) -> None:
        """
        Show error for invalid selection.

        Override to customize error message.

        Args:
            path: Invalid path that was selected
        """
        self.notify(f"Invalid selection: {path.name}", severity="error")

    def _validate_selection(self) -> bool:
        """
        Validate current selection before confirming.

        Override to add additional validation. Default checks _is_valid_selection.

        Returns:
            True if selection is valid, False otherwise
        """
        return self._is_valid_selection(self.selected_path)

    # =================================================================
    # Template Methods - Implemented in base class
    # =================================================================

    def compose(self) -> ComposeResult:
        """Create the browser layout."""
        with Vertical():
            yield Label(self._get_title(), id="title")
            yield FilteredDirectoryTree(str(self.start_dir), id="tree")
            yield Input(
                value=str(self.start_dir),
                placeholder="Enter or paste directory path...",
                id="path-input",
            )

            # Allow subclasses to add extra widgets
            extra_widgets = self._get_extra_widgets()
            if extra_widgets:
                with Container(id="extra-widgets"):
                    yield from extra_widgets

            yield Label(self._get_instructions(), id="instructions")

            with Horizontal(id="button-row"):
                yield from self._get_buttons()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection in tree."""
        self._on_tree_directory_selected(event)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in tree."""
        self._on_tree_file_selected(event)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle path input submission (Enter key in input field)."""
        if event.input.id == "path-input":
            self._navigate_to_path(event.value)

    def on_input_blurred(self, event: Input.Blurred) -> None:
        """Handle input losing focus - navigate to the entered path."""
        if event.input.id == "path-input":
            self._navigate_to_path(event.input.value)

    def _navigate_to_path(self, path_str: str) -> None:
        """
        Navigate to a path entered in the input field.

        Args:
            path_str: The path string from the input field
        """
        entered_path = Path(path_str.strip())
        if entered_path.exists() and entered_path.is_dir():
            # Valid directory - navigate to it
            self.run_worker(self._navigate_to_directory(entered_path))
        else:
            # Invalid path - revert to current path and show error
            path_input = self.query_one("#path-input", Input)
            path_input.value = str(self.selected_path)
            self.notify(f"Invalid directory: {entered_path}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "select-btn":
            self._confirm_selection()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_select_current(self) -> None:
        """Select the currently highlighted item."""
        tree = self.query_one("#tree", DirectoryTree)
        if tree.cursor_node and tree.cursor_node.data:
            cursor_path = Path(str(tree.cursor_node.data.path))
            self.selected_path = cursor_path
            self._confirm_selection()
        else:
            # Fallback to selected_path if no cursor
            self._confirm_selection()

    def _confirm_selection(self) -> None:
        """Confirm the current selection and dismiss."""
        if self._validate_selection():
            selection_value = self._get_selection_value()
            self.dismiss(selection_value)
        else:
            self._show_invalid_selection_error(self.selected_path)

    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)

    async def _navigate_to_directory(self, new_path: Path) -> None:
        """
        Navigate to a new directory by reloading the tree.

        Args:
            new_path: The directory to navigate to
        """
        # Remove the old tree and wait for it to be removed
        old_tree = self.query_one("#tree", DirectoryTree)
        await old_tree.remove()

        # Create and mount a new tree with the new path
        new_tree = FilteredDirectoryTree(str(new_path), id="tree")

        # Find the vertical container and insert the tree after the title
        container = self.query_one(Vertical)
        title = self.query_one("#title", Label)
        await container.mount(new_tree, after=title)

        # Update the path input
        path_input = self.query_one("#path-input", Input)
        path_input.value = str(new_path)

        # Update selected_path
        self.selected_path = new_path

        # Set focus on the new tree and move cursor to root node
        new_tree.focus()
        if new_tree.root:
            new_tree.move_cursor(new_tree.root)
            new_tree.select_node(new_tree.root)

    def on_key(self, event: events.Key) -> None:
        """Handle key presses - intercept enter for selection, left/right for navigation."""
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.action_select_current()
        elif event.key == "right":
            # Expand the current node (step into folder)
            tree = self.query_one("#tree", DirectoryTree)
            if tree.cursor_node and not tree.cursor_node.is_expanded:
                tree.cursor_node.expand()
                event.prevent_default()
                event.stop()
        elif event.key == "left":
            # Collapse current node, go to parent, or navigate up past root
            tree = self.query_one("#tree", DirectoryTree)
            if tree.cursor_node:
                if tree.cursor_node.is_expanded:
                    # If expanded, collapse it
                    tree.cursor_node.collapse()
                    event.prevent_default()
                    event.stop()
                elif tree.cursor_node.parent:
                    # If collapsed, move to parent
                    tree.select_node(tree.cursor_node.parent)
                    event.prevent_default()
                    event.stop()
                elif tree.cursor_node.data:
                    # We're at the root node, navigate up one directory level
                    current_path = Path(str(tree.cursor_node.data.path))
                    parent_path = current_path.parent
                    if parent_path != current_path:  # Make sure we're not at filesystem root
                        self.run_worker(self._navigate_to_directory(parent_path))
                        event.prevent_default()
                        event.stop()
