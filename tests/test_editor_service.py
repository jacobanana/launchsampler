"""Unit tests for EditorService."""

from pathlib import Path

import pytest

from launchsampler.models import AppConfig, Color, Launchpad, PlaybackMode
from launchsampler.tui.services import EditorService


class TestEditorServiceCopyPad:
    """Test copy_pad method."""

    @pytest.fixture
    def launchpad(self):
        """Create a fresh launchpad for each test."""
        return Launchpad.create_empty()

    @pytest.fixture
    def config(self, temp_dir):
        """Create test config."""
        return AppConfig(sets_dir=temp_dir)

    @pytest.fixture
    def editor(self, launchpad, config):
        """Create editor service."""
        return EditorService(launchpad, config)

    @pytest.mark.unit
    def test_copy_pad_success(self, editor, sample_audio_file):
        """Test successful copy of a pad with sample."""
        # Assign sample to source pad
        source_index = 5
        target_index = 10
        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.7)
        editor.set_pad_mode(source_index, PlaybackMode.LOOP)

        # Copy to target
        result = editor.copy_pad(source_index, target_index)

        # Verify target has same properties
        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        assert target_pad.is_assigned
        assert target_pad.sample.name == source_pad.sample.name
        assert target_pad.sample.path == source_pad.sample.path
        assert target_pad.mode == PlaybackMode.LOOP
        assert target_pad.volume == 0.7
        assert target_pad.color == source_pad.color

        # Verify position is preserved
        assert target_pad.x == 2  # target_index 10 = (2, 1)
        assert target_pad.y == 1
        assert result == target_pad

    @pytest.mark.unit
    def test_copy_pad_creates_deep_copy(self, editor, sample_audio_file):
        """Test that copy creates new objects, not references."""
        source_index = 0
        target_index = 1

        # Setup source pad
        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.8)

        # Copy to target
        editor.copy_pad(source_index, target_index)

        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        # Verify objects are not the same instance
        assert source_pad.sample is not target_pad.sample
        assert source_pad.color is not target_pad.color

        # Modify target's sample name
        editor.set_sample_name(target_index, "modified_name")

        # Verify source was not affected
        assert source_pad.sample.name == "test"
        assert target_pad.sample.name == "modified_name"

        # Modify target's color
        target_pad.color = Color(r=50, g=50, b=50)

        # Verify source color unchanged
        assert source_pad.color.r == 127  # ONE_SHOT default red
        assert target_pad.color.r == 50

    @pytest.mark.unit
    def test_copy_pad_preserves_target_position(self, editor, sample_audio_file):
        """Test that target position (x, y) is preserved after copy."""
        source_index = 7  # (7, 0)
        target_index = 56  # (0, 7)

        editor.assign_sample(source_index, sample_audio_file)
        editor.copy_pad(source_index, target_index)

        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        # Source position unchanged
        assert source_pad.x == 7
        assert source_pad.y == 0

        # Target position unchanged
        assert target_pad.x == 0
        assert target_pad.y == 7

    @pytest.mark.unit
    def test_copy_pad_overwrites_existing_target(self, editor, sample_audio_file, temp_dir):
        """Test that copying overwrites target pad if it has a sample."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        source_index = 0
        target_index = 1

        # Assign different samples to both pads
        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.6)
        editor.assign_sample(target_index, second_file)
        editor.set_pad_volume(target_index, 0.9)

        # Copy source to target
        editor.copy_pad(source_index, target_index)

        target_pad = editor.get_pad(target_index)

        # Target should now have source's sample and properties
        assert target_pad.sample.name == "test"
        assert target_pad.volume == 0.6
        assert target_pad.sample.path == sample_audio_file

    @pytest.mark.unit
    def test_copy_pad_source_out_of_range(self, editor):
        """Test that invalid source index raises IndexError."""
        with pytest.raises(IndexError, match=r"Source pad index 64 out of range \(0-63\)"):
            editor.copy_pad(64, 0)

        with pytest.raises(IndexError, match=r"Source pad index -1 out of range \(0-63\)"):
            editor.copy_pad(-1, 0)

    @pytest.mark.unit
    def test_copy_pad_target_out_of_range(self, editor):
        """Test that invalid target index raises IndexError."""
        with pytest.raises(IndexError, match=r"Target pad index 64 out of range \(0-63\)"):
            editor.copy_pad(0, 64)

        with pytest.raises(IndexError, match=r"Target pad index -1 out of range \(0-63\)"):
            editor.copy_pad(0, -1)

    @pytest.mark.unit
    def test_copy_pad_same_index(self, editor, sample_audio_file):
        """Test that copying to same index raises ValueError."""
        editor.assign_sample(0, sample_audio_file)

        with pytest.raises(ValueError, match="Source and target pads must be different"):
            editor.copy_pad(0, 0)

    @pytest.mark.unit
    def test_copy_pad_empty_source(self, editor):
        """Test that copying from empty pad raises ValueError."""
        with pytest.raises(ValueError, match="Source pad 0 has no sample to copy"):
            editor.copy_pad(0, 1)

    @pytest.mark.unit
    def test_copy_pad_all_modes(self, editor, sample_audio_file):
        """Test copying pads with different playback modes."""
        modes = [
            PlaybackMode.ONE_SHOT,
            PlaybackMode.LOOP,
            PlaybackMode.HOLD,
            PlaybackMode.LOOP_TOGGLE,
        ]

        for i, mode in enumerate(modes):
            source_index = i
            target_index = i + 10

            editor.assign_sample(source_index, sample_audio_file)
            editor.set_pad_mode(source_index, mode)

            editor.copy_pad(source_index, target_index)

            target_pad = editor.get_pad(target_index)
            assert target_pad.mode == mode
            assert target_pad.color == mode.get_default_color()

    @pytest.mark.unit
    def test_copy_pad_volume_independence(self, editor, sample_audio_file):
        """Test that volume changes on target don't affect source."""
        source_index = 0
        target_index = 1

        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.5)

        editor.copy_pad(source_index, target_index)

        # Change target volume
        editor.set_pad_volume(target_index, 1.0)

        # Verify source unchanged
        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        assert source_pad.volume == 0.5
        assert target_pad.volume == 1.0

    @pytest.mark.unit
    def test_copy_pad_overwrite_false_empty_target(self, editor, sample_audio_file):
        """Test copying with overwrite=False to empty target succeeds."""
        source_index = 0
        target_index = 1

        editor.assign_sample(source_index, sample_audio_file)

        # Should succeed - target is empty
        result = editor.copy_pad(source_index, target_index, overwrite=False)

        target_pad = editor.get_pad(target_index)
        assert target_pad.is_assigned
        assert target_pad.sample.name == "test"
        assert result == target_pad

    @pytest.mark.unit
    def test_copy_pad_overwrite_false_occupied_target(self, editor, sample_audio_file, temp_dir):
        """Test copying with overwrite=False to occupied target raises ValueError."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        source_index = 0
        target_index = 1

        # Assign samples to both pads
        editor.assign_sample(source_index, sample_audio_file)
        editor.assign_sample(target_index, second_file)

        # Should fail - target already has a sample
        with pytest.raises(
            ValueError,
            match=r"Target pad 1 already has sample 'second'"
        ):
            editor.copy_pad(source_index, target_index, overwrite=False)

        # Verify target was not modified
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "second"

    @pytest.mark.unit
    def test_copy_pad_overwrite_true_occupied_target(self, editor, sample_audio_file, temp_dir):
        """Test copying with overwrite=True to occupied target succeeds."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        source_index = 0
        target_index = 1

        # Assign samples to both pads
        editor.assign_sample(source_index, sample_audio_file)
        editor.assign_sample(target_index, second_file)

        # Should succeed - overwrite=True (default)
        result = editor.copy_pad(source_index, target_index, overwrite=True)

        # Verify target now has source's sample
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "test"
        assert target_pad.sample.path == sample_audio_file
        assert result == target_pad

    @pytest.mark.unit
    def test_copy_pad_default_overwrite_behavior(self, editor, sample_audio_file, temp_dir):
        """Test that overwrite defaults to False (safe mode)."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        source_index = 0
        target_index = 1

        # Assign samples to both pads
        editor.assign_sample(source_index, sample_audio_file)
        editor.assign_sample(target_index, second_file)

        # Should fail with default parameters (overwrite=False by default)
        with pytest.raises(
            ValueError,
            match=r"Target pad 1 already has sample 'second'"
        ):
            editor.copy_pad(source_index, target_index)

        # Verify target was NOT modified
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "second"
