"""Unit tests for Pydantic models."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from launchsampler.models import (
    AppConfig,
    Color,
    Launchpad,
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

    @pytest.mark.unit
    def test_from_sample_directory(self, temp_dir):
        """Test creating Launchpad from sample directory."""
        # Create test audio files with different naming conventions
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        # Create files with different naming patterns
        files = [
            ("kick_oneshot.wav", PlaybackMode.ONE_SHOT),
            ("bass_loop.wav", PlaybackMode.LOOP),
            ("pad_tone.wav", PlaybackMode.LOOP),
            ("vocal_hold.wav", PlaybackMode.HOLD),
        ]

        for filename, _ in files:
            sf.write(str(temp_dir / filename), audio_data, sample_rate)

        # Test auto-configuration
        launchpad = Launchpad.from_sample_directory(
            temp_dir, auto_configure=True, default_volume=0.5
        )

        # Verify correct number of samples loaded
        assert len(launchpad.assigned_pads) == 4

        # Verify auto-configuration worked correctly
        pad0 = launchpad.pads[0]  # bass_loop (alphabetically first)
        assert pad0.is_assigned
        assert pad0.mode == PlaybackMode.LOOP
        assert pad0.color == Color(r=0, g=127, b=0)  # Green
        assert pad0.volume == 0.5

        pad1 = launchpad.pads[1]  # kick_oneshot
        assert pad1.mode == PlaybackMode.ONE_SHOT
        assert pad1.color == Color(r=127, g=0, b=0)  # Red

        pad2 = launchpad.pads[2]  # pad_tone
        assert pad2.mode == PlaybackMode.LOOP
        assert pad2.color == Color(r=0, g=127, b=0)  # Green

        pad3 = launchpad.pads[3]  # vocal_hold
        assert pad3.mode == PlaybackMode.HOLD
        assert pad3.color == Color(r=0, g=0, b=127)  # Blue

    @pytest.mark.unit
    def test_from_sample_directory_no_auto_configure(self, temp_dir):
        """Test creating Launchpad without auto-configuration."""
        # Create a test audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        sf.write(str(temp_dir / "test_loop.wav"), audio_data, sample_rate)

        launchpad = Launchpad.from_sample_directory(
            temp_dir, auto_configure=False, default_volume=0.8
        )

        # Should still use ONE_SHOT as default even with "loop" in name
        pad0 = launchpad.pads[0]
        assert pad0.mode == PlaybackMode.ONE_SHOT
        assert pad0.color == Color(r=127, g=0, b=0)  # Red (ONE_SHOT default)
        assert pad0.volume == 0.8

    @pytest.mark.unit
    def test_from_sample_directory_invalid_path(self):
        """Test that invalid directory raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            Launchpad.from_sample_directory(Path("/nonexistent/path"))

    @pytest.mark.unit
    def test_from_sample_directory_no_files(self, temp_dir):
        """Test that directory with no audio files raises ValueError."""
        with pytest.raises(ValueError, match="No audio files found"):
            Launchpad.from_sample_directory(temp_dir)


class TestPlaybackMode:
    """Test PlaybackMode enum."""

    @pytest.mark.unit
    def test_get_default_color(self):
        """Test getting default colors for playback modes."""
        # ONE_SHOT should be red
        assert PlaybackMode.ONE_SHOT.get_default_color() == Color(r=127, g=0, b=0)

        # LOOP should be green
        assert PlaybackMode.LOOP.get_default_color() == Color(r=0, g=127, b=0)

        # HOLD should be blue
        assert PlaybackMode.HOLD.get_default_color() == Color(r=0, g=0, b=127)

        # LOOP_TOGGLE should be magenta
        assert PlaybackMode.LOOP_TOGGLE.get_default_color() == Color(r=127, g=0, b=127)


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

    @pytest.mark.unit
    def test_save_detects_common_path(self, temp_dir):
        """Test that save_to_file detects and uses common path as samples_root."""
        # Create sample directory structure
        samples_dir = temp_dir / "samples" / "drums"
        samples_dir.mkdir(parents=True)

        # Create test audio files
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        kick_path = samples_dir / "kick.wav"
        snare_path = samples_dir / "snare.wav"
        sf.write(str(kick_path), audio_data, sample_rate)
        sf.write(str(snare_path), audio_data, sample_rate)

        # Create set with samples from common directory
        my_set = Set.create_empty("test_set")
        my_set.launchpad.pads[0].sample = Sample.from_file(kick_path)
        my_set.launchpad.pads[1].sample = Sample.from_file(snare_path)

        # Save to a different location
        save_path = temp_dir / "sets" / "my_set.json"
        save_path.parent.mkdir(parents=True)
        my_set.save_to_file(save_path)

        # Verify samples_root was set to common path
        assert my_set.samples_root == samples_dir

        # Verify paths remain absolute in memory (bug fix - paths should not be mutated)
        assert my_set.launchpad.pads[0].sample.path.is_absolute()
        assert my_set.launchpad.pads[1].sample.path.is_absolute()
        assert my_set.launchpad.pads[0].sample.path == kick_path
        assert my_set.launchpad.pads[1].sample.path == snare_path
        
        # Verify that the saved file contains relative paths
        import json
        saved_data = json.loads(save_path.read_text())
        assert saved_data['launchpad']['pads'][0]['sample']['path'] == "kick.wav"
        assert saved_data['launchpad']['pads'][1]['sample']['path'] == "snare.wav"

    @pytest.mark.unit
    def test_save_with_nested_samples(self, temp_dir):
        """Test saving when samples are in nested subdirectories.

        When samples are under the Set file's directory, samples_root is None
        and paths are relative to the Set file.
        """
        # Create nested directory structure
        samples_root = temp_dir / "samples"
        drums_dir = samples_root / "drums"
        bass_dir = samples_root / "bass"
        drums_dir.mkdir(parents=True)
        bass_dir.mkdir(parents=True)

        # Create test audio files
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        kick_path = drums_dir / "kick.wav"
        bass_path = bass_dir / "bass.wav"
        sf.write(str(kick_path), audio_data, sample_rate)
        sf.write(str(bass_path), audio_data, sample_rate)

        # Create set
        my_set = Set.create_empty("test_set")
        my_set.launchpad.pads[0].sample = Sample.from_file(kick_path)
        my_set.launchpad.pads[1].sample = Sample.from_file(bass_path)

        # Save to temp_dir (parent of samples directory)
        save_path = temp_dir / "my_set.json"
        my_set.save_to_file(save_path)

        # Verify samples_root is None (because samples are under Set directory)
        assert my_set.samples_root is None

        # Verify paths remain absolute in memory (bug fix - paths should not be mutated)
        assert my_set.launchpad.pads[0].sample.path.is_absolute()
        assert my_set.launchpad.pads[1].sample.path.is_absolute()
        assert my_set.launchpad.pads[0].sample.path == kick_path
        assert my_set.launchpad.pads[1].sample.path == bass_path
        
        # Verify that the saved file contains relative paths
        import json
        saved_data = json.loads(save_path.read_text())
        # Normalize path separators for cross-platform comparison
        assert Path(saved_data['launchpad']['pads'][0]['sample']['path']) == Path("samples/drums/kick.wav")
        assert Path(saved_data['launchpad']['pads'][1]['sample']['path']) == Path("samples/bass/bass.wav")

    @pytest.mark.unit
    def test_load_resolves_relative_paths(self, temp_dir):
        """Test that loading a set resolves relative paths correctly."""
        # Create sample directory structure
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir(parents=True)

        # Create test audio files
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        kick_path = samples_dir / "kick.wav"
        sf.write(str(kick_path), audio_data, sample_rate)

        # Create and save set
        my_set = Set.create_empty("test_set")
        my_set.launchpad.pads[0].sample = Sample.from_file(kick_path)
        save_path = temp_dir / "my_set.json"
        my_set.save_to_file(save_path)

        # Load set
        loaded = Set.load_from_file(save_path)

        # Verify path was resolved to absolute
        assert loaded.launchpad.pads[0].sample.path.is_absolute()
        assert loaded.launchpad.pads[0].sample.path == kick_path

    @pytest.mark.unit
    def test_save_with_no_samples(self, temp_dir):
        """Test saving an empty set (no samples assigned)."""
        my_set = Set.create_empty("test_set")
        save_path = temp_dir / "empty.json"
        my_set.save_to_file(save_path)

        # Verify it doesn't crash and samples_root is None
        assert my_set.samples_root is None

        # Load and verify
        loaded = Set.load_from_file(save_path)
        assert loaded.name == "test_set"
        assert loaded.samples_root is None

    @pytest.mark.unit
    def test_save_with_samples_under_set_directory(self, temp_dir):
        """Test edge case: samples are in subdirectory of Set file location.

        When samples are stored in a subdirectory relative to the Set file,
        samples_root should be None (for portability) and paths should be
        relative to the Set file location.
        """
        # Create structure: temp_dir/my_set.json and temp_dir/samples/kick.wav
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # Create test audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        kick_path = samples_dir / "kick.wav"
        sf.write(str(kick_path), audio_data, sample_rate)

        # Create set
        my_set = Set.create_empty("test_set")
        my_set.launchpad.pads[0].sample = Sample.from_file(kick_path)

        # Save in parent directory
        save_path = temp_dir / "my_set.json"
        my_set.save_to_file(save_path)

        # Verify samples_root is None (relative to Set file)
        assert my_set.samples_root is None

        # Verify path remains absolute in memory (bug fix - paths should not be mutated)
        assert my_set.launchpad.pads[0].sample.path.is_absolute()
        assert my_set.launchpad.pads[0].sample.path == kick_path
        
        # Verify that the saved file contains relative path
        import json
        saved_data = json.loads(save_path.read_text())
        # Normalize path separators for cross-platform comparison
        assert Path(saved_data['launchpad']['pads'][0]['sample']['path']) == Path("samples/kick.wav")

        # Load and verify it resolves correctly
        loaded = Set.load_from_file(save_path)
        assert loaded.launchpad.pads[0].sample.path == kick_path

    @pytest.mark.unit
    def test_save_with_samples_outside_set_directory(self, temp_dir):
        """Test that samples outside Set directory still use absolute samples_root."""
        # Create structure where samples are NOT under the set directory
        set_dir = temp_dir / "sets"
        samples_dir = temp_dir / "my_samples"
        set_dir.mkdir()
        samples_dir.mkdir()

        # Create test audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        kick_path = samples_dir / "kick.wav"
        sf.write(str(kick_path), audio_data, sample_rate)

        # Create set
        my_set = Set.create_empty("test_set")
        my_set.launchpad.pads[0].sample = Sample.from_file(kick_path)

        # Save in different directory
        save_path = set_dir / "my_set.json"
        my_set.save_to_file(save_path)

        # Verify samples_root is set to the samples directory
        assert my_set.samples_root == samples_dir

        # Verify path remains absolute in memory (bug fix - paths should not be mutated)
        assert my_set.launchpad.pads[0].sample.path.is_absolute()
        assert my_set.launchpad.pads[0].sample.path == kick_path
        
        # Verify that the saved file contains relative path to samples_root
        import json
        saved_data = json.loads(save_path.read_text())
        assert saved_data['launchpad']['pads'][0]['sample']['path'] == "kick.wav"

        # Load and verify
        loaded = Set.load_from_file(save_path)
        assert loaded.launchpad.pads[0].sample.path == kick_path


class TestAppConfig:
    """Test AppConfig model."""

    @pytest.mark.unit
    def test_default_config(self):
        """Test creating default config."""
        config = AppConfig()
        assert config.default_buffer_size == 512
        assert config.default_audio_device is None

    @pytest.mark.unit
    def test_load_or_default(self, temp_dir):
        """Test loading config or creating default."""
        # Non-existent file should return default
        config = AppConfig.load_or_default(temp_dir / "nonexistent.json")
        assert config.default_buffer_size == 512

    @pytest.mark.unit
    def test_save_and_load(self, temp_dir):
        """Test saving and loading config."""
        config = AppConfig(default_buffer_size=256)
        save_path = temp_dir / "config.json"
        config.save(save_path)

        # Load and verify
        loaded = AppConfig.load_or_default(save_path)
        assert loaded.default_buffer_size == 256
