"""Path utility functions."""

from pathlib import Path
from typing import Optional


def find_common_path(paths: list[Path]) -> Optional[Path]:
    """Find the most specific common parent path shared by all paths.

    Args:
        paths: List of Path objects (can be absolute or relative)

    Returns:
        The deepest common parent directory, or None if paths is empty

    Examples:
        >>> find_common_path([Path('/a/b/c.wav'), Path('/a/b/d.wav')])
        Path('/a/b')
        >>> find_common_path([Path('/a/b/c.wav'), Path('/x/y/z.wav')])
        Path('/')
    """
    if not paths:
        return None

    # Convert all paths to absolute for comparison
    abs_paths = [p.resolve() for p in paths]

    # Get all parent parts for each path
    all_parts = [list(p.parents)[::-1] + [p.parent] for p in abs_paths]

    # Find common prefix by comparing parts
    if not all_parts:
        return None

    common = abs_paths[0].parent
    for path in abs_paths[1:]:
        # Find the common ancestor between current common and this path
        try:
            # Try to make path relative to common - if it works, common is still valid
            path.relative_to(common)
        except ValueError:
            # Path is not under common, need to go up
            # Find the actual common ancestor
            while common != common.parent:  # Don't go above root
                try:
                    path.relative_to(common)
                    break
                except ValueError:
                    common = common.parent

    return common
