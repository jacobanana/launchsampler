"""Unit tests for Pydantic models."""

from pathlib import Path

import pytest

from launchsampler.models import (
    AppConfig,
    Color,
    Launchpad,
    LaunchpadModel,
    Pad,
    PlaybackMode,
    Sample,
    Set,
)


class TestColor:
    """Test Color model."""

    @pytest.mark.unit
    def test_create_color(self):
        """Test creating a color with RGB values."""
        color = Color(r=100, g=50, b=25)
        assert color.r == 100
        assert color.g == 50
        assert color.b == 25

    @pytest.mark.unit
    def test_rgb_range_validation(self):
        """Test that RGB values must be 0-127."""
        with pytest.raises(ValueError):
            Color(r=128, g=0, b=0)

        with pytest.raises(ValueError):
            Color(r=0, g=-1, b=0)

    @pytest.mark.unit
    def test_preset_color_off(self):
        """Test off color factory method."""
        assert Color.off() == Color(r=0, g=0, b=0)

    @pytest.mark.unit
    def test_to_rgb_tuple(self):
        """Test RGB tuple conversion."""
        color = Color(r=10, g=20, b=30)
        assert color.to_rgb_tuple() == (10, 20, 30)


class TestSample:
    """Test Sample model."""

    @pytest.mark.unit
    def test_from_file(self, sample_audio_file):
        """Test creating Sample from file path."""
        sample = Sample.from_file(sample_audio_file)
        assert sample.name == "test"
        assert sample.path == sample_audio_file

    @pytest.mark.unit
    def test_exists(self, sample_audio_file):
        """Test checking if sample file exists."""
        sample = Sample.from_file(sample_audio_file)
        assert sample.exists() is True

        nonexistent = Sample(name="fake", path=Path("nonexistent.wav"))
        assert nonexistent.exists() is False


class TestPad:
    """Test Pad model."""

    @pytest.mark.unit
    def test_create_empty_pad(self):
        """Test creating an empty pad."""
        pad = Pad.empty(x=3, y=5)
        assert pad.x == 3
        assert pad.y == 5
        assert pad.sample is None
        assert pad.is_assigned is False

    @pytest.mark.unit
    def test_coordinate_validation(self):
        """Test that coordinates must be 0-7."""
        with pytest.raises(ValueError):
            Pad(x=8, y=0)

        with pytest.raises(ValueError):
            Pad(x=0, y=-1)

    @pytest.mark.unit
    def test_assign_sample(self, pad_empty, sample_model):
        """Test assigning a sample to a pad."""
        pad_empty.sample = sample_model
        assert pad_empty.is_assigned is True
        assert pad_empty.sample == sample_model

    @pytest.mark.unit
    def test_position_property(self):
        """Test position tuple property."""
        pad = Pad(x=2, y=4)
        assert pad.position == (2, 4)

    @pytest.mark.unit
    def test_clear_pad(self, pad_with_sample):
        """Test clearing a pad."""
        assert pad_with_sample.is_assigned is True
        pad_with_sample.clear()
        assert pad_with_sample.is_assigned is False
        assert pad_with_sample.color == Color.off()


class TestLaunchpad:
    """Test Launchpad model."""

    @pytest.mark.unit
    def test_create_empty(self):
        """Test creating empty launchpad."""
        launchpad = Launchpad.create_empty()
        assert len(launchpad.pads) == 64
        assert all(not pad.is_assigned for pad in launchpad.pads)

    @pytest.mark.unit
    def test_get_pad(self):
        """Test getting pad by coordinates."""
        launchpad = Launchpad.create_empty()
        pad = launchpad.get_pad(3, 5)
        assert pad.x == 3
        assert pad.y == 5

    @pytest.mark.unit
    def test_get_pad_invalid_coordinates(self):
        """Test that invalid coordinates raise error."""
        launchpad = Launchpad.create_empty()
        with pytest.raises(ValueError):
            launchpad.get_pad(8, 0)

    @pytest.mark.unit
    def test_note_to_xy_conversion(self):
        """Test MIDI note to coordinate conversion."""
        launchpad = Launchpad.create_empty()
        assert launchpad.note_to_xy(0) == (0, 0)
        assert launchpad.note_to_xy(7) == (7, 0)
        assert launchpad.note_to_xy(8) == (0, 1)
        assert launchpad.note_to_xy(63) == (7, 7)

    @pytest.mark.unit
    def test_xy_to_note_conversion(self):
        """Test coordinate to MIDI note conversion."""
        launchpad = Launchpad.create_empty()
        assert launchpad.xy_to_note(0, 0) == 0
        assert launchpad.xy_to_note(7, 0) == 7
        assert launchpad.xy_to_note(0, 1) == 8
        assert launchpad.xy_to_note(7, 7) == 63

    @pytest.mark.unit
    def test_assigned_pads(self, sample_model):
        """Test getting list of assigned pads."""
        launchpad = Launchpad.create_empty()
        assert len(launchpad.assigned_pads) == 0

        launchpad.get_pad(0, 0).sample = sample_model
        launchpad.get_pad(1, 1).sample = sample_model
        assert len(launchpad.assigned_pads) == 2


class TestSet:
    """Test Set model."""

    @pytest.mark.unit
    def test_create_empty(self):
        """Test creating empty set."""
        my_set = Set.create_empty("test_set")
        assert my_set.name == "test_set"
        assert len(my_set.launchpad.pads) == 64

    @pytest.mark.unit
    def test_save_and_load(self, temp_dir):
        """Test saving and loading a set."""
        # Create and save
        my_set = Set.create_empty("test_set")
        save_path = temp_dir / "test.json"
        my_set.save_to_file(save_path)

        # Load and verify
        loaded = Set.load_from_file(save_path)
        assert loaded.name == "test_set"
        assert len(loaded.launchpad.pads) == 64


class TestAppConfig:
    """Test AppConfig model."""

    @pytest.mark.unit
    def test_default_config(self):
        """Test creating default config."""
        config = AppConfig()
        assert config.sample_rate == 44100
        assert config.buffer_size == 512
        assert config.launchpad_model == LaunchpadModel.LAUNCHPAD_X

    @pytest.mark.unit
    def test_load_or_default(self, temp_dir):
        """Test loading config or creating default."""
        # Non-existent file should return default
        config = AppConfig.load_or_default(temp_dir / "nonexistent.json")
        assert config.sample_rate == 44100

    @pytest.mark.unit
    def test_save_and_load(self, temp_dir):
        """Test saving and loading config."""
        config = AppConfig(sample_rate=48000, buffer_size=256)
        save_path = temp_dir / "config.json"
        config.save(save_path)

        # Load and verify
        loaded = AppConfig.load_or_default(save_path)
        assert loaded.sample_rate == 48000
        assert loaded.buffer_size == 256
