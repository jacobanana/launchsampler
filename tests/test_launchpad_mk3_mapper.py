"""Unit tests for Launchpad MK3 Mapper (pure calculation/mapping functions)."""

import pytest

from launchsampler.devices.adapters.launchpad_mk3 import LaunchpadMK3Mapper
from launchsampler.devices.config import DeviceConfig
from launchsampler.devices.schema import DeviceCapabilities


@pytest.fixture
def mk3_mapper():
    """Create a Launchpad MK3 mapper for testing."""
    config = DeviceConfig(
        family="launchpad_mk3",
        model="Launchpad MK3",
        manufacturer="Novation",
        implements="launchpad_mk3",
        capabilities=DeviceCapabilities(
            num_pads=64,
            grid_size=8,
            supports_sysex=True,
            supports_rgb=True,
        ),
        sysex_header=[0x00, 0x20, 0x29, 0x02, 0x0E],
    )
    return LaunchpadMK3Mapper(config)


class TestLaunchpadMK3Mapper:
    """Test LaunchpadMK3Mapper coordinate and note mapping functions."""

    @pytest.mark.unit
    def test_note_to_xy_bottom_left(self, mk3_mapper):
        """Test note to xy conversion for bottom-left pad."""
        # Note 11 = bottom-left corner (0, 0)
        x, y = mk3_mapper.note_to_xy(11)
        assert (x, y) == (0, 0)

    @pytest.mark.unit
    def test_note_to_xy_bottom_right(self, mk3_mapper):
        """Test note to xy conversion for bottom-right pad."""
        # Note 18 = bottom-right corner (7, 0)
        x, y = mk3_mapper.note_to_xy(18)
        assert (x, y) == (7, 0)

    @pytest.mark.unit
    def test_note_to_xy_top_left(self, mk3_mapper):
        """Test note to xy conversion for top-left pad."""
        # Note 81 = top-left corner (0, 7)
        x, y = mk3_mapper.note_to_xy(81)
        assert (x, y) == (0, 7)

    @pytest.mark.unit
    def test_note_to_xy_top_right(self, mk3_mapper):
        """Test note to xy conversion for top-right pad."""
        # Note 88 = top-right corner (7, 7)
        x, y = mk3_mapper.note_to_xy(88)
        assert (x, y) == (7, 7)

    @pytest.mark.unit
    def test_note_to_xy_middle(self, mk3_mapper):
        """Test note to xy conversion for middle pad."""
        # Note 44 = middle-ish (3, 3)
        # 44 - 11 = 33
        # row = 33 // 10 = 3
        # col = 33 % 10 = 3
        x, y = mk3_mapper.note_to_xy(44)
        assert (x, y) == (3, 3)

    @pytest.mark.unit
    def test_note_to_xy_invalid_note_too_low(self, mk3_mapper):
        """Test note to xy returns None for note below range."""
        x, y = mk3_mapper.note_to_xy(10)
        assert (x, y) == (None, None)

    @pytest.mark.unit
    def test_note_to_xy_invalid_note_too_high(self, mk3_mapper):
        """Test note to xy returns None for note above range."""
        x, y = mk3_mapper.note_to_xy(89)
        assert (x, y) == (None, None)

    @pytest.mark.unit
    def test_note_to_xy_invalid_note_gap(self, mk3_mapper):
        """Test note to xy returns None for gap notes (19, 29, etc)."""
        # Note 19 is in a gap (not a valid pad)
        x, y = mk3_mapper.note_to_xy(19)
        assert (x, y) == (None, None)

        # Note 29 is also in a gap
        x, y = mk3_mapper.note_to_xy(29)
        assert (x, y) == (None, None)

    @pytest.mark.unit
    def test_xy_to_note_bottom_left(self, mk3_mapper):
        """Test xy to note conversion for bottom-left pad."""
        note = mk3_mapper.xy_to_note(0, 0)
        assert note == 11

    @pytest.mark.unit
    def test_xy_to_note_bottom_right(self, mk3_mapper):
        """Test xy to note conversion for bottom-right pad."""
        note = mk3_mapper.xy_to_note(7, 0)
        assert note == 18

    @pytest.mark.unit
    def test_xy_to_note_top_left(self, mk3_mapper):
        """Test xy to note conversion for top-left pad."""
        note = mk3_mapper.xy_to_note(0, 7)
        assert note == 81

    @pytest.mark.unit
    def test_xy_to_note_top_right(self, mk3_mapper):
        """Test xy to note conversion for top-right pad."""
        note = mk3_mapper.xy_to_note(7, 7)
        assert note == 88

    @pytest.mark.unit
    def test_xy_to_note_middle(self, mk3_mapper):
        """Test xy to note conversion for middle pad."""
        note = mk3_mapper.xy_to_note(3, 3)
        assert note == 44

    @pytest.mark.unit
    def test_xy_to_note_invalid_x_negative(self, mk3_mapper):
        """Test xy to note returns None for negative x."""
        note = mk3_mapper.xy_to_note(-1, 0)
        assert note is None

    @pytest.mark.unit
    def test_xy_to_note_invalid_x_too_high(self, mk3_mapper):
        """Test xy to note returns None for x >= 8."""
        note = mk3_mapper.xy_to_note(8, 0)
        assert note is None

    @pytest.mark.unit
    def test_xy_to_note_invalid_y_negative(self, mk3_mapper):
        """Test xy to note returns None for negative y."""
        note = mk3_mapper.xy_to_note(0, -1)
        assert note is None

    @pytest.mark.unit
    def test_xy_to_note_invalid_y_too_high(self, mk3_mapper):
        """Test xy to note returns None for y >= 8."""
        note = mk3_mapper.xy_to_note(0, 8)
        assert note is None

    @pytest.mark.unit
    def test_index_to_note_first_pad(self, mk3_mapper):
        """Test index to note conversion for first pad (index 0)."""
        note = mk3_mapper.index_to_note(0)
        assert note == 11  # Bottom-left

    @pytest.mark.unit
    def test_index_to_note_last_pad(self, mk3_mapper):
        """Test index to note conversion for last pad (index 63)."""
        note = mk3_mapper.index_to_note(63)
        assert note == 88  # Top-right

    @pytest.mark.unit
    def test_index_to_note_middle(self, mk3_mapper):
        """Test index to note conversion for middle pad."""
        # Index 27 = row 3, col 3 = note 44
        note = mk3_mapper.index_to_note(27)
        assert note == 44

    @pytest.mark.unit
    def test_index_to_note_invalid_negative(self, mk3_mapper):
        """Test index to note returns None for negative index."""
        note = mk3_mapper.index_to_note(-1)
        assert note is None

    @pytest.mark.unit
    def test_index_to_note_invalid_too_high(self, mk3_mapper):
        """Test index to note returns None for index >= 64."""
        note = mk3_mapper.index_to_note(64)
        assert note is None

    @pytest.mark.unit
    def test_note_to_index_first_pad(self, mk3_mapper):
        """Test note to index conversion for first pad."""
        index = mk3_mapper.note_to_index(11)
        assert index == 0

    @pytest.mark.unit
    def test_note_to_index_last_pad(self, mk3_mapper):
        """Test note to index conversion for last pad."""
        index = mk3_mapper.note_to_index(88)
        assert index == 63

    @pytest.mark.unit
    def test_note_to_index_middle(self, mk3_mapper):
        """Test note to index conversion for middle pad."""
        # Note 44 = (3, 3) = index 27
        index = mk3_mapper.note_to_index(44)
        assert index == 27

    @pytest.mark.unit
    def test_note_to_index_invalid(self, mk3_mapper):
        """Test note to index returns None for invalid note."""
        index = mk3_mapper.note_to_index(19)  # Gap note
        assert index is None

    @pytest.mark.unit
    def test_roundtrip_index_to_note_to_index(self, mk3_mapper):
        """Test roundtrip conversion from index to note and back."""
        for index in range(64):
            note = mk3_mapper.index_to_note(index)
            assert note is not None

            recovered_index = mk3_mapper.note_to_index(note)
            assert recovered_index == index

    @pytest.mark.unit
    def test_roundtrip_xy_to_note_to_xy(self, mk3_mapper):
        """Test roundtrip conversion from xy to note and back."""
        for y in range(8):
            for x in range(8):
                note = mk3_mapper.xy_to_note(x, y)
                assert note is not None

                recovered_x, recovered_y = mk3_mapper.note_to_xy(note)
                assert (recovered_x, recovered_y) == (x, y)

    @pytest.mark.unit
    def test_mapper_constants(self, mk3_mapper):
        """Test mapper uses correct programmer mode constants."""
        assert mk3_mapper.offset == 11
        assert mk3_mapper.row_spacing == 10
        assert mk3_mapper.PROGRAMMER_MODE_OFFSET == 11
        assert mk3_mapper.PROGRAMMER_MODE_ROW_SPACING == 10
