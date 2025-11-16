"""Unit tests for LaunchpadNoteMapper."""

import pytest
from launchsampler.devices.launchpad import LaunchpadModel, LaunchpadNoteMapper


class TestLaunchpadNoteMapper:
    """Test note mapping between MIDI notes and pad indices."""

    @pytest.fixture
    def mapper(self):
        """Create a LaunchpadNoteMapper for testing."""
        return LaunchpadNoteMapper(LaunchpadModel.MINI_MK3)

    def test_note_to_index_bottom_left(self, mapper):
        """Test that note 11 maps to index 0 (bottom-left)."""
        assert mapper.note_to_index(11) == 0

    def test_note_to_index_bottom_right(self, mapper):
        """Test that note 18 maps to index 7 (bottom-right)."""
        assert mapper.note_to_index(18) == 7

    def test_note_to_index_top_left(self, mapper):
        """Test that note 81 maps to index 56 (top-left)."""
        assert mapper.note_to_index(81) == 56

    def test_note_to_index_top_right(self, mapper):
        """Test that note 88 maps to index 63 (top-right)."""
        assert mapper.note_to_index(88) == 63

    def test_note_to_index_invalid_note(self, mapper):
        """Test that invalid notes return None."""
        assert mapper.note_to_index(0) is None
        assert mapper.note_to_index(10) is None
        assert mapper.note_to_index(89) is None
        assert mapper.note_to_index(127) is None

    def test_note_to_index_invalid_column(self, mapper):
        """Test that notes with invalid columns return None."""
        # Note 19 would be row 0, column 8 (invalid)
        assert mapper.note_to_index(19) is None
        # Note 29 would be row 1, column 8 (invalid)
        assert mapper.note_to_index(29) is None

    def test_note_to_xy_bottom_left(self, mapper):
        """Test that note 11 maps to (0, 0)."""
        assert mapper.note_to_xy(11) == (0, 0)

    def test_note_to_xy_bottom_right(self, mapper):
        """Test that note 18 maps to (7, 0)."""
        assert mapper.note_to_xy(18) == (7, 0)

    def test_note_to_xy_top_left(self, mapper):
        """Test that note 81 maps to (0, 7)."""
        assert mapper.note_to_xy(81) == (0, 7)

    def test_note_to_xy_top_right(self, mapper):
        """Test that note 88 maps to (7, 7)."""
        assert mapper.note_to_xy(88) == (7, 7)

    def test_note_to_xy_middle(self, mapper):
        """Test middle positions."""
        # Note 44 = 11 + 3*10 + 3 = row 3, col 3
        assert mapper.note_to_xy(44) == (3, 3)
        # Note 55 = 11 + 4*10 + 4 = row 4, col 4
        assert mapper.note_to_xy(55) == (4, 4)

    def test_note_to_xy_invalid(self, mapper):
        """Test that invalid notes return (None, None)."""
        assert mapper.note_to_xy(0) == (None, None)
        assert mapper.note_to_xy(10) == (None, None)
        assert mapper.note_to_xy(89) == (None, None)
        assert mapper.note_to_xy(19) == (None, None)  # Invalid column

    def test_index_to_note_bottom_left(self, mapper):
        """Test that index 0 maps to note 11."""
        assert mapper.index_to_note(0) == 11

    def test_index_to_note_bottom_right(self, mapper):
        """Test that index 7 maps to note 18."""
        assert mapper.index_to_note(7) == 18

    def test_index_to_note_top_left(self, mapper):
        """Test that index 56 maps to note 81."""
        assert mapper.index_to_note(56) == 81

    def test_index_to_note_top_right(self, mapper):
        """Test that index 63 maps to note 88."""
        assert mapper.index_to_note(63) == 88

    def test_index_to_note_middle(self, mapper):
        """Test middle positions."""
        # Index 27 = row 3, col 3 → note 44
        assert mapper.index_to_note(27) == 44
        # Index 36 = row 4, col 4 → note 55
        assert mapper.index_to_note(36) == 55

    def test_index_to_note_invalid(self, mapper):
        """Test that invalid indices return None."""
        assert mapper.index_to_note(-1) is None
        assert mapper.index_to_note(64) is None
        assert mapper.index_to_note(100) is None

    def test_xy_to_note_corners(self, mapper):
        """Test corner positions."""
        assert mapper.xy_to_note(0, 0) == 11  # Bottom-left
        assert mapper.xy_to_note(7, 0) == 18  # Bottom-right
        assert mapper.xy_to_note(0, 7) == 81  # Top-left
        assert mapper.xy_to_note(7, 7) == 88  # Top-right

    def test_xy_to_note_middle(self, mapper):
        """Test middle positions."""
        assert mapper.xy_to_note(3, 3) == 44
        assert mapper.xy_to_note(4, 4) == 55

    def test_xy_to_note_invalid(self, mapper):
        """Test that invalid coordinates return None."""
        assert mapper.xy_to_note(-1, 0) is None
        assert mapper.xy_to_note(0, -1) is None
        assert mapper.xy_to_note(8, 0) is None
        assert mapper.xy_to_note(0, 8) is None
        assert mapper.xy_to_note(10, 10) is None

    def test_bidirectional_mapping(self, mapper):
        """Test that mapping is bidirectional for all valid indices."""
        for index in range(64):
            note = mapper.index_to_note(index)
            assert note is not None
            assert mapper.note_to_index(note) == index

    def test_all_models_use_same_mapping(self):
        """Test that all models use the same programmer mode mapping."""
        mappers = [
            LaunchpadNoteMapper(LaunchpadModel.X),
            LaunchpadNoteMapper(LaunchpadModel.MINI_MK3),
            LaunchpadNoteMapper(LaunchpadModel.PRO_MK3),
        ]

        for mapper in mappers:
            assert mapper.note_to_index(11) == 0
            assert mapper.note_to_index(88) == 63
            assert mapper.index_to_note(0) == 11
            assert mapper.index_to_note(63) == 88
