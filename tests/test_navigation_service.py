"""Tests for NavigationService - Grid navigation logic."""

import pytest

from launchsampler.models import Launchpad
from launchsampler.tui.services import NavigationService


class TestNavigationService:
    """Test suite for NavigationService grid navigation."""

    @pytest.fixture
    def launchpad(self) -> Launchpad:
        """Create a fresh Launchpad for each test."""
        return Launchpad.create_empty()

    @pytest.fixture
    def nav(self, launchpad: Launchpad) -> NavigationService:
        """Create NavigationService instance."""
        return NavigationService(launchpad)

    # =================================================================
    # Test: Basic Navigation - Cardinal Directions
    # =================================================================

    def test_navigate_right_from_origin(self, nav: NavigationService) -> None:
        """Test navigating right from bottom-left corner (pad 0)."""
        # Pad 0 is at (0, 0) - bottom-left
        result = nav.get_neighbor(0, "right")
        assert result == 1  # Pad at (1, 0)

    def test_navigate_up_from_origin(self, nav: NavigationService) -> None:
        """Test navigating up from bottom-left corner (pad 0)."""
        # Pad 0 is at (0, 0)
        result = nav.get_neighbor(0, "up")
        assert result == 8  # Pad at (0, 1) - one row up

    def test_navigate_left_from_pad_1(self, nav: NavigationService) -> None:
        """Test navigating left back to origin."""
        result = nav.get_neighbor(1, "left")
        assert result == 0

    def test_navigate_down_from_pad_8(self, nav: NavigationService) -> None:
        """Test navigating down from second row."""
        result = nav.get_neighbor(8, "down")
        assert result == 0

    # =================================================================
    # Test: Edge Detection - Grid Boundaries
    # =================================================================

    def test_navigate_left_from_left_edge_returns_none(self, nav: NavigationService) -> None:
        """Test that navigating left from left edge returns None."""
        # Pad 0 is at left edge (x=0)
        result = nav.get_neighbor(0, "left")
        assert result is None

    def test_navigate_down_from_bottom_edge_returns_none(self, nav: NavigationService) -> None:
        """Test that navigating down from bottom edge returns None."""
        # Pad 0 is at bottom edge (y=0)
        result = nav.get_neighbor(0, "down")
        assert result is None

    def test_navigate_right_from_right_edge_returns_none(self, nav: NavigationService) -> None:
        """Test that navigating right from right edge returns None."""
        # Pad 7 is at right edge (x=7, y=0)
        result = nav.get_neighbor(7, "right")
        assert result is None

    def test_navigate_up_from_top_edge_returns_none(self, nav: NavigationService) -> None:
        """Test that navigating up from top edge returns None."""
        # Pad 63 is at top-right corner (x=7, y=7)
        result = nav.get_neighbor(63, "up")
        assert result is None

    # =================================================================
    # Test: Corner Cases - All Four Corners
    # =================================================================

    def test_bottom_left_corner_pad_0(self, nav: NavigationService) -> None:
        """Test navigation from bottom-left corner (0,0)."""
        # Can only move right or up
        assert nav.get_neighbor(0, "right") == 1
        assert nav.get_neighbor(0, "up") == 8
        assert nav.get_neighbor(0, "left") is None
        assert nav.get_neighbor(0, "down") is None

    def test_bottom_right_corner_pad_7(self, nav: NavigationService) -> None:
        """Test navigation from bottom-right corner (7,0)."""
        # Can only move left or up
        assert nav.get_neighbor(7, "left") == 6
        assert nav.get_neighbor(7, "up") == 15
        assert nav.get_neighbor(7, "right") is None
        assert nav.get_neighbor(7, "down") is None

    def test_top_left_corner_pad_56(self, nav: NavigationService) -> None:
        """Test navigation from top-left corner (0,7)."""
        # Can only move right or down
        assert nav.get_neighbor(56, "right") == 57
        assert nav.get_neighbor(56, "down") == 48
        assert nav.get_neighbor(56, "left") is None
        assert nav.get_neighbor(56, "up") is None

    def test_top_right_corner_pad_63(self, nav: NavigationService) -> None:
        """Test navigation from top-right corner (7,7)."""
        # Can only move left or down
        assert nav.get_neighbor(63, "left") == 62
        assert nav.get_neighbor(63, "down") == 55
        assert nav.get_neighbor(63, "right") is None
        assert nav.get_neighbor(63, "up") is None

    # =================================================================
    # Test: Middle of Grid - All Directions Valid
    # =================================================================

    def test_navigate_from_center_all_directions(self, nav: NavigationService) -> None:
        """Test that center pad can navigate in all directions."""
        # Pad 27 is near center (x=3, y=3)
        center_pad = 27

        # All directions should be valid
        assert nav.get_neighbor(center_pad, "up") == 35  # (3, 4)
        assert nav.get_neighbor(center_pad, "down") == 19  # (3, 2)
        assert nav.get_neighbor(center_pad, "left") == 26  # (2, 3)
        assert nav.get_neighbor(center_pad, "right") == 28  # (4, 3)

    # =================================================================
    # Test: Edge Positions - Boundary Detection
    # =================================================================

    def test_get_edge_position_corner_bottom_left(self, nav: NavigationService) -> None:
        """Test edge detection for bottom-left corner."""
        edges = nav.get_edge_position(0)
        assert edges == {"left", "bottom"}

    def test_get_edge_position_corner_top_right(self, nav: NavigationService) -> None:
        """Test edge detection for top-right corner."""
        edges = nav.get_edge_position(63)
        assert edges == {"right", "top"}

    def test_get_edge_position_left_edge_middle(self, nav: NavigationService) -> None:
        """Test edge detection for left edge (not corner)."""
        edges = nav.get_edge_position(24)  # (0, 3) - left edge, middle
        assert edges == {"left"}

    def test_get_edge_position_right_edge_middle(self, nav: NavigationService) -> None:
        """Test edge detection for right edge (not corner)."""
        edges = nav.get_edge_position(31)  # (7, 3) - right edge, middle
        assert edges == {"right"}

    def test_get_edge_position_top_edge_middle(self, nav: NavigationService) -> None:
        """Test edge detection for top edge (not corner)."""
        edges = nav.get_edge_position(60)  # (4, 7) - top edge, middle
        assert edges == {"top"}

    def test_get_edge_position_bottom_edge_middle(self, nav: NavigationService) -> None:
        """Test edge detection for bottom edge (not corner)."""
        edges = nav.get_edge_position(4)  # (4, 0) - bottom edge, middle
        assert edges == {"bottom"}

    def test_get_edge_position_center(self, nav: NavigationService) -> None:
        """Test edge detection for center pad (no edges)."""
        edges = nav.get_edge_position(27)  # (3, 3) - center
        assert edges == set()

    # =================================================================
    # Test: can_move Helper Method
    # =================================================================

    def test_can_move_valid_direction(self, nav: NavigationService) -> None:
        """Test can_move returns True for valid moves."""
        assert nav.can_move(0, "right") is True
        assert nav.can_move(0, "up") is True

    def test_can_move_invalid_direction(self, nav: NavigationService) -> None:
        """Test can_move returns False for invalid moves."""
        assert nav.can_move(0, "left") is False
        assert nav.can_move(0, "down") is False

    def test_can_move_invalid_pad_index(self, nav: NavigationService) -> None:
        """Test can_move returns False for out-of-range pad index."""
        assert nav.can_move(-1, "up") is False
        assert nav.can_move(64, "right") is False
        assert nav.can_move(100, "down") is False

    # =================================================================
    # Test: Error Handling - Invalid Input
    # =================================================================

    def test_get_neighbor_invalid_pad_index_negative(self, nav: NavigationService) -> None:
        """Test that negative pad index raises ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            nav.get_neighbor(-1, "up")

    def test_get_neighbor_invalid_pad_index_too_large(self, nav: NavigationService) -> None:
        """Test that pad index >= 64 raises ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            nav.get_neighbor(64, "right")

    def test_get_neighbor_invalid_direction_returns_none(self, nav: NavigationService) -> None:
        """Test that invalid direction returns None (not an error)."""
        result = nav.get_neighbor(0, "diagonal")  # type: ignore
        assert result is None

    def test_get_edge_position_invalid_pad_index_negative(self, nav: NavigationService) -> None:
        """Test that get_edge_position raises ValueError for negative index."""
        with pytest.raises(ValueError, match="out of range"):
            nav.get_edge_position(-1)

    def test_get_edge_position_invalid_pad_index_too_large(self, nav: NavigationService) -> None:
        """Test that get_edge_position raises ValueError for index >= 64."""
        with pytest.raises(ValueError, match="out of range"):
            nav.get_edge_position(64)

    # =================================================================
    # Test: Grid Coordinate Consistency
    # =================================================================

    def test_navigate_sequence_right_then_up(self, nav: NavigationService) -> None:
        """Test that navigation sequence is consistent with grid layout."""
        # Start at pad 0 (0,0)
        # Move right to pad 1 (1,0)
        pad_1 = nav.get_neighbor(0, "right")
        assert pad_1 == 1

        # Move up to pad 9 (1,1)
        pad_9 = nav.get_neighbor(pad_1, "up")
        assert pad_9 == 9

    def test_navigate_sequence_up_then_right(self, nav: NavigationService) -> None:
        """Test that different navigation order reaches same pad."""
        # Start at pad 0 (0,0)
        # Move up to pad 8 (0,1)
        pad_8 = nav.get_neighbor(0, "up")
        assert pad_8 == 8

        # Move right to pad 9 (1,1)
        pad_9 = nav.get_neighbor(pad_8, "right")
        assert pad_9 == 9

    def test_navigate_round_trip(self, nav: NavigationService) -> None:
        """Test that navigating away and back returns to origin."""
        # Start at center pad 27 (3,3)
        start_pad = 27

        # Move right, then left - should return to start
        right_pad = nav.get_neighbor(start_pad, "right")
        back_pad = nav.get_neighbor(right_pad, "left")
        assert back_pad == start_pad

        # Move up, then down - should return to start
        up_pad = nav.get_neighbor(start_pad, "up")
        down_pad = nav.get_neighbor(up_pad, "down")
        assert down_pad == start_pad
