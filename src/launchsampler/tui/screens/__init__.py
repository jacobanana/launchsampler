"""Modal screens for dialogs."""

from .base_browser import BaseBrowserScreen
from .file_browser import FileBrowserScreen
from .directory_browser import DirectoryBrowserScreen
from .set_file_browser import SetFileBrowserScreen
from .save_set_browser import SaveSetBrowserScreen

# Legacy screens - deprecated, use browser-based screens instead
from .save_set import SaveSetScreen
from .load_set import LoadSetScreen

__all__ = [
    "BaseBrowserScreen",
    "FileBrowserScreen",
    "DirectoryBrowserScreen",
    "SetFileBrowserScreen",
    "SaveSetBrowserScreen",
    # Legacy - deprecated
    "SaveSetScreen",
    "LoadSetScreen",
]
