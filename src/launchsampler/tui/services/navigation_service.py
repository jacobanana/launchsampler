"""Grid navigation service for directional pad operations.

This service handles pure grid geometry logic for navigating the 8x8 Launchpad grid.
It is UI-agnostic and can be reused by different UI implementations (TUI, LED UI, etc.).

Responsibilities:
- Calculate neighboring pad indices in cardinal directions (up, down, left, right)
- Validate grid boundaries before navigation
- Pure functions with no side effects

Design Principles:
- Single Responsibility: Only grid geometry, no UI or business logic
- Testable: No dependencies on Textual or UI framework
- Reusable: Can be used by TUI, LED UI, or any other UI implementation
"""

import logging
from typing import Literal

from launchsampler.models import Launchpad

logger = logging.getLogger(__name__)

# Type alias for direction
Direction = Literal["up", "down", "left", "right"]


class NavigationService:
    """
    Service for navigating the Launchpad 8x8 grid.

    This service provides pure functions for calculating neighboring pad indices
    in cardinal directions. It respects grid boundaries and returns None when
    attempting to navigate beyond the grid edge.

    Example:
        >>> nav = NavigationService(launchpad)
        >>> nav.get_neighbor(0, "right")  # Pad 0 -> Pad 1
        1
        >>> nav.get_neighbor(0, "down")   # Pad 0 -> None (at bottom edge)
        None
        >>> nav.get_neighbor(63, "up")    # Pad 63 -> None (at top edge)
        None
    """

    def __init__(self, launchpad: Launchpad):
        """
        Initialize the navigation service.

        Args:
            launchpad: The Launchpad grid to navigate
        """
        self.launchpad = launchpad
        self._grid_size = launchpad.GRID_SIZE

    def get_neighbor(self, pad_index: int, direction: Direction) -> int | None:
        """
        Get the neighboring pad index in the given direction.

        Validates grid boundaries and returns None if the move would go beyond
        the grid edge. Uses the same coordinate system as the Launchpad:
        - X axis: left (0) to right (7)
        - Y axis: bottom (0) to top (7)
        - Index 0 is bottom-left, index 63 is top-right

        Args:
            pad_index: Current pad index (0-63)
            direction: Direction to move ("up", "down", "left", "right")

        Returns:
            Target pad index, or None if at edge (cannot move in that direction)

        Raises:
            ValueError: If pad_index is out of range (not 0-63)
        """
        if not 0 <= pad_index < self.launchpad.TOTAL_PADS:
            raise ValueError(f"Pad index {pad_index} out of range (must be 0-63)")

        # Convert to grid coordinates
        x, y = self.launchpad.note_to_xy(pad_index)

        # Calculate new coordinates based on direction
        # Check bounds BEFORE calculating target (fail fast)
        if direction == "up":
            if y >= self._grid_size - 1:  # Already at top edge
                return None
            y = y + 1
        elif direction == "down":
            if y <= 0:  # Already at bottom edge
                return None
            y = y - 1
        elif direction == "left":
            if x <= 0:  # Already at left edge
                return None
            x = x - 1
        elif direction == "right":
            if x >= self._grid_size - 1:  # Already at right edge
                return None
            x = x + 1
        else:
            logger.warning(f"Invalid direction: {direction}")
            return None

        # Convert back to pad index
        return self.launchpad.xy_to_note(x, y)

    def can_move(self, pad_index: int, direction: Direction) -> bool:
        """
        Check if a move in the given direction is valid (not at edge).

        This is a convenience method that combines get_neighbor with a boolean check.

        Args:
            pad_index: Current pad index (0-63)
            direction: Direction to check ("up", "down", "left", "right")

        Returns:
            True if move is valid, False if at edge or invalid input
        """
        try:
            return self.get_neighbor(pad_index, direction) is not None
        except ValueError:
            return False

    def get_edge_position(self, pad_index: int) -> set[str]:
        """
        Get which edges this pad is on.

        Useful for UI feedback (e.g., showing disabled directional arrows).

        Args:
            pad_index: Pad index to check (0-63)

        Returns:
            Set of edge names (e.g., {"left", "bottom"} for pad 0)

        Raises:
            ValueError: If pad_index is out of range
        """
        if not 0 <= pad_index < self.launchpad.TOTAL_PADS:
            raise ValueError(f"Pad index {pad_index} out of range (must be 0-63)")

        x, y = self.launchpad.note_to_xy(pad_index)
        edges = set()

        if x == 0:
            edges.add("left")
        if x == self._grid_size - 1:
            edges.add("right")
        if y == 0:
            edges.add("bottom")
        if y == self._grid_size - 1:
            edges.add("top")

        return edges
