"""Load set screen for selecting saved configurations."""

from pathlib import Path

from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, ListView, ListItem
from textual.binding import Binding

from launchsampler.models import Set


class LoadSetScreen(Screen):
    """
    Screen for loading a saved set.

    Displays a list of available sets from the sets directory
    and allows selection.
    """

    DEFAULT_CSS = """
    LoadSetScreen {
        align: center middle;
    }

    LoadSetScreen > Vertical {
        width: 60;
        height: 40;
        background: $surface;
        border: thick $primary;
        padding: 2;
    }

    LoadSetScreen Label {
        margin-bottom: 1;
    }

    LoadSetScreen ListView {
        height: 25;
        border: solid $primary;
        margin-bottom: 1;
    }

    LoadSetScreen Horizontal {
        height: auto;
        align: center middle;
    }

    LoadSetScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "load_selected", "Load"),
    ]

    def __init__(self, sets_dir: Path) -> None:
        """
        Initialize load set screen.

        Args:
            sets_dir: Directory containing saved sets
        """
        super().__init__()
        self.sets_dir = sets_dir
        self.set_files: list[Path] = []

    def compose(self) -> ComposeResult:
        """Create the load dialog layout."""
        with Vertical():
            yield Label("[b]Load Set[/b]")
            yield Label("Select a set to load:")
            yield ListView(id="sets-list")
            with Horizontal():
                yield Button("Load", id="load-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Populate the list when mounted."""
        list_view = self.query_one("#sets-list", ListView)

        # Find all .json files in sets directory
        if self.sets_dir.exists():
            self.set_files = sorted(self.sets_dir.glob("*.json"))

            if self.set_files:
                for set_file in self.set_files:
                    # Load set to get metadata
                    try:
                        set_obj = Set.load_from_file(set_file)
                        assigned_count = len(set_obj.launchpad.assigned_pads)
                        created = set_obj.created_at.strftime("%Y-%m-%d %H:%M")
                        list_view.append(
                            ListItem(
                                Label(
                                    f"[cyan]{set_obj.name}[/cyan] - "
                                    f"{assigned_count} pads - {created}"
                                )
                            )
                        )
                    except Exception:
                        # Fallback if can't load set
                        list_view.append(
                            ListItem(
                                Label(f"[dim]{set_file.stem}[/dim] (error loading)")
                            )
                        )
            else:
                list_view.append(
                    ListItem(Label("[dim]No saved sets found[/dim]"))
                )
        else:
            list_view.append(
                ListItem(Label("[dim]No saved sets found[/dim]"))
            )

    def action_load_selected(self) -> None:
        """Load the selected set."""
        list_view = self.query_one("#sets-list", ListView)
        if list_view.index is not None and list_view.index < len(self.set_files):
            self.dismiss(self.set_files[list_view.index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "load-btn":
            list_view = self.query_one("#sets-list", ListView)
            if list_view.index is not None and list_view.index < len(self.set_files):
                self.dismiss(self.set_files[list_view.index])
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the screen."""
        self.dismiss(None)
