"""Directory browser screen for loading samples from a folder."""

from pathlib import Path

from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, DirectoryTree, Input
from textual.binding import Binding
from textual import events


class DirectoryBrowserScreen(Screen):
    """
    Screen for browsing and selecting directories containing samples.

    Displays a directory tree and allows selection of directories.
    User can select a directory by pressing Enter on it or using
    the "Select" button.
    """

    # Make this a modal screen to prevent parent app shortcuts from interfering
    MODAL = True

    DEFAULT_CSS = """
    DirectoryBrowserScreen {
        align: center middle;
    }

    DirectoryBrowserScreen > Vertical {
        width: 100;
        height: 45;
        background: $surface;
        border: thick $primary;
    }

    DirectoryBrowserScreen #instructions {
        height: auto;
        width: 100%;
        background: $boost;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    DirectoryBrowserScreen DirectoryTree {
        height: 25;
        border: solid $primary;
        margin: 1;
    }

    DirectoryBrowserScreen #path-input {
        height: 3;
        border: solid $primary;
        margin: 1;
    }

    DirectoryBrowserScreen Horizontal {
        height: 3;
        align: center middle;
        margin: 1;
    }

    DirectoryBrowserScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "select_current", "Select Directory", priority=True),
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
        Initialize directory browser.

        Args:
            start_dir: Directory to start browsing from
        """
        super().__init__()
        self.start_dir = start_dir
        self.selected_path: Path = start_dir

    def compose(self) -> ComposeResult:
        """Create the directory browser layout."""
        with Vertical():
            yield Label("[b]Open Directory[/b]", id="title")
            yield DirectoryTree(str(self.start_dir), id="tree")
            yield Input(
                value=str(self.start_dir),
                placeholder="Enter or paste directory path...",
                id="path-input"
            )
            yield Label(
                "[b]Tree Navigation:[/b] ↑↓: navigate | →: expand | ←: collapse/up | Enter: select\n"
                "[b]Path Input:[/b] Type/paste path above, then Tab or Enter to navigate",
                id="instructions"
            )
            with Horizontal():
                yield Button("Select", id="select-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """
        Handle directory highlighting in the tree.

        This fires when a directory node is clicked or navigated to,
        but doesn't select it - just updates the path input.
        """
        self.selected_path = Path(event.path)
        path_input = self.query_one("#path-input", Input)
        path_input.value = str(self.selected_path)

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
            self.dismiss(self.selected_path)
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_select_current(self) -> None:
        """Select the currently highlighted directory."""
        # Get the currently highlighted node from the DirectoryTree
        tree = self.query_one("#tree", DirectoryTree)
        if tree.cursor_node:
            # Use the path from the cursor node, not self.selected_path
            cursor_path = Path(str(tree.cursor_node.data.path))
            self.dismiss(cursor_path)
        else:
            # Fallback to selected_path if no cursor
            self.dismiss(self.selected_path)

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
        new_tree = DirectoryTree(str(new_path), id="tree")

        # Find the vertical container and insert the tree after the title
        # (before path-input which comes after the tree in the layout)
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
                else:
                    # We're at the root node, navigate up one directory level
                    current_path = Path(str(tree.cursor_node.data.path))
                    parent_path = current_path.parent
                    if parent_path != current_path:  # Make sure we're not at filesystem root
                        self.run_worker(self._navigate_to_directory(parent_path))
                        event.prevent_default()
                        event.stop()
