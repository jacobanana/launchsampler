"""Unit tests for EditorService."""

from pathlib import Path

import pytest

from launchsampler.models import AppConfig, Color, Launchpad, PlaybackMode
from launchsampler.tui.services import EditorService


class TestEditorServiceDuplicatePad:
    """Test duplicate_pad method."""

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
    def test_duplicate_pad_success(self, editor, sample_audio_file):
        """Test successful copy of a pad with sample."""
        # Assign sample to source pad
        source_index = 5
        target_index = 10
        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.7)
        editor.set_pad_mode(source_index, PlaybackMode.LOOP)

        # Copy to target
        result = editor.duplicate_pad(source_index, target_index)

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
    def test_duplicate_pad_creates_deep_copy(self, editor, sample_audio_file):
        """Test that copy creates new objects, not references."""
        source_index = 0
        target_index = 1

        # Setup source pad
        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.8)

        # Copy to target
        editor.duplicate_pad(source_index, target_index)

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
    def test_duplicate_pad_preserves_target_position(self, editor, sample_audio_file):
        """Test that target position (x, y) is preserved after copy."""
        source_index = 7  # (7, 0)
        target_index = 56  # (0, 7)

        editor.assign_sample(source_index, sample_audio_file)
        editor.duplicate_pad(source_index, target_index)

        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        # Source position unchanged
        assert source_pad.x == 7
        assert source_pad.y == 0

        # Target position unchanged
        assert target_pad.x == 0
        assert target_pad.y == 7

    @pytest.mark.unit
    def test_duplicate_pad_overwrites_existing_target(self, editor, sample_audio_file, temp_dir):
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
        editor.duplicate_pad(source_index, target_index)

        target_pad = editor.get_pad(target_index)

        # Target should now have source's sample and properties
        assert target_pad.sample.name == "test"
        assert target_pad.volume == 0.6
        assert target_pad.sample.path == sample_audio_file

    @pytest.mark.unit
    def test_duplicate_pad_source_out_of_range(self, editor):
        """Test that invalid source index raises IndexError."""
        with pytest.raises(IndexError, match=r"Source pad index 64 out of range \(0-63\)"):
            editor.duplicate_pad(64, 0)

        with pytest.raises(IndexError, match=r"Source pad index -1 out of range \(0-63\)"):
            editor.duplicate_pad(-1, 0)

    @pytest.mark.unit
    def test_duplicate_pad_target_out_of_range(self, editor):
        """Test that invalid target index raises IndexError."""
        with pytest.raises(IndexError, match=r"Target pad index 64 out of range \(0-63\)"):
            editor.duplicate_pad(0, 64)

        with pytest.raises(IndexError, match=r"Target pad index -1 out of range \(0-63\)"):
            editor.duplicate_pad(0, -1)

    @pytest.mark.unit
    def test_duplicate_pad_same_index(self, editor, sample_audio_file):
        """Test that copying to same index raises ValueError."""
        editor.assign_sample(0, sample_audio_file)

        with pytest.raises(ValueError, match="Source and target pads must be different"):
            editor.duplicate_pad(0, 0)

    @pytest.mark.unit
    def test_duplicate_pad_empty_source(self, editor):
        """Test that copying from empty pad raises ValueError."""
        with pytest.raises(ValueError, match="Source pad 0 has no sample to copy"):
            editor.duplicate_pad(0, 1)

    @pytest.mark.unit
    def test_duplicate_pad_all_modes(self, editor, sample_audio_file):
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

            editor.duplicate_pad(source_index, target_index)

            target_pad = editor.get_pad(target_index)
            assert target_pad.mode == mode
            assert target_pad.color == mode.get_default_color()

    @pytest.mark.unit
    def test_duplicate_pad_volume_independence(self, editor, sample_audio_file):
        """Test that volume changes on target don't affect source."""
        source_index = 0
        target_index = 1

        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.5)

        editor.duplicate_pad(source_index, target_index)

        # Change target volume
        editor.set_pad_volume(target_index, 1.0)

        # Verify source unchanged
        source_pad = editor.get_pad(source_index)
        target_pad = editor.get_pad(target_index)

        assert source_pad.volume == 0.5
        assert target_pad.volume == 1.0

    @pytest.mark.unit
    def test_duplicate_pad_overwrite_false_empty_target(self, editor, sample_audio_file):
        """Test copying with overwrite=False to empty target succeeds."""
        source_index = 0
        target_index = 1

        editor.assign_sample(source_index, sample_audio_file)

        # Should succeed - target is empty
        result = editor.duplicate_pad(source_index, target_index, overwrite=False)

        target_pad = editor.get_pad(target_index)
        assert target_pad.is_assigned
        assert target_pad.sample.name == "test"
        assert result == target_pad

    @pytest.mark.unit
    def test_duplicate_pad_overwrite_false_occupied_target(self, editor, sample_audio_file, temp_dir):
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
            editor.duplicate_pad(source_index, target_index, overwrite=False)

        # Verify target was not modified
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "second"

    @pytest.mark.unit
    def test_duplicate_pad_overwrite_true_occupied_target(self, editor, sample_audio_file, temp_dir):
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
        result = editor.duplicate_pad(source_index, target_index, overwrite=True)

        # Verify target now has source's sample
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "test"
        assert target_pad.sample.path == sample_audio_file
        assert result == target_pad

    @pytest.mark.unit
    def test_duplicate_pad_default_overwrite_behavior(self, editor, sample_audio_file, temp_dir):
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
            editor.duplicate_pad(source_index, target_index)

        # Verify target was NOT modified
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "second"


class TestEditorServiceCopyPaste:
    """Test copy_pad and paste_pad clipboard methods."""

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
        """Test copying a pad to clipboard."""
        pad_index = 5
        editor.assign_sample(pad_index, sample_audio_file)
        editor.set_pad_volume(pad_index, 0.7)
        editor.set_pad_mode(pad_index, PlaybackMode.LOOP)

        result = editor.copy_pad(pad_index)

        # Verify clipboard contains the copied pad
        assert result.sample.name == "test"
        assert result.volume == 0.7
        assert result.mode == PlaybackMode.LOOP

    @pytest.mark.unit
    def test_copy_empty_pad(self, editor):
        """Test that copying empty pad raises ValueError."""
        with pytest.raises(ValueError, match="Cannot copy empty pad 0"):
            editor.copy_pad(0)

    @pytest.mark.unit
    def test_copy_pad_out_of_range(self, editor):
        """Test that invalid pad index raises IndexError."""
        with pytest.raises(IndexError, match=r"Pad index 64 out of range \(0-63\)"):
            editor.copy_pad(64)

    @pytest.mark.unit
    def test_paste_pad_success(self, editor, sample_audio_file):
        """Test pasting from clipboard to empty target."""
        source_index = 0
        target_index = 5

        editor.assign_sample(source_index, sample_audio_file)
        editor.set_pad_volume(source_index, 0.8)
        editor.copy_pad(source_index)

        result = editor.paste_pad(target_index)

        # Verify target has clipboard contents
        target_pad = editor.get_pad(target_index)
        assert target_pad.sample.name == "test"
        assert target_pad.volume == 0.8
        assert target_pad.x == 5  # Position preserved
        assert target_pad.y == 0
        assert result == target_pad

    @pytest.mark.unit
    def test_paste_empty_clipboard(self, editor):
        """Test that pasting with empty clipboard raises ValueError."""
        with pytest.raises(ValueError, match="Clipboard is empty. Copy a pad first."):
            editor.paste_pad(5)

    @pytest.mark.unit
    def test_paste_overwrite_false_occupied_target(self, editor, sample_audio_file, temp_dir):
        """Test pasting with overwrite=False to occupied target raises ValueError."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        # Copy pad 0
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)

        # Assign to target
        editor.assign_sample(5, second_file)

        # Should fail - target occupied
        with pytest.raises(
            ValueError,
            match=r"Target pad 5 already has sample 'second'"
        ):
            editor.paste_pad(5, overwrite=False)

    @pytest.mark.unit
    def test_paste_overwrite_true_occupied_target(self, editor, sample_audio_file, temp_dir):
        """Test pasting with overwrite=True to occupied target succeeds."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        # Copy pad 0
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)

        # Assign to target
        editor.assign_sample(5, second_file)

        # Should succeed
        result = editor.paste_pad(5, overwrite=True)

        target_pad = editor.get_pad(5)
        assert target_pad.sample.name == "test"
        assert result == target_pad

    @pytest.mark.unit
    def test_paste_multiple_times(self, editor, sample_audio_file):
        """Test that clipboard can be pasted multiple times."""
        editor.assign_sample(0, sample_audio_file)
        editor.set_pad_volume(0, 0.6)
        editor.copy_pad(0)

        # Paste to multiple targets
        editor.paste_pad(1)
        editor.paste_pad(2)
        editor.paste_pad(3)

        # All targets should have the same sample
        for i in [1, 2, 3]:
            pad = editor.get_pad(i)
            assert pad.sample.name == "test"
            assert pad.volume == 0.6

    @pytest.mark.unit
    def test_copy_overwrites_clipboard(self, editor, sample_audio_file, temp_dir):
        """Test that copying a new pad overwrites clipboard."""
        import numpy as np
        import soundfile as sf

        # Create second audio file
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        second_file = temp_dir / "second.wav"
        sf.write(str(second_file), audio_data, sample_rate)

        # Copy first pad
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)

        # Copy second pad (overwrites clipboard)
        editor.assign_sample(1, second_file)
        editor.copy_pad(1)

        # Paste should use second pad
        editor.paste_pad(5)
        target_pad = editor.get_pad(5)
        assert target_pad.sample.name == "second"

    @pytest.mark.unit
    def test_paste_creates_independent_copy(self, editor, sample_audio_file):
        """Test that pasted pad is independent from clipboard."""
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)
        editor.paste_pad(1)

        # Modify target
        editor.set_pad_volume(1, 0.3)

        # Copy again and paste to another location
        editor.paste_pad(2)

        # Second paste should have original volume, not modified
        pad2 = editor.get_pad(2)
        assert pad2.volume == 0.8  # Original default volume
