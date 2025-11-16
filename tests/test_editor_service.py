"""Unit tests for EditorService."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from launchsampler.models import AppConfig, Color, Launchpad, PlaybackMode
from launchsampler.protocols import EditEvent, EditObserver
from launchsampler.services import EditorService


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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

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

        # Copy source to target with overwrite enabled
        editor.duplicate_pad(source_index, target_index, overwrite=True)

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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

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


class TestEditorServiceCutPad:
    """Test cut_pad clipboard method."""

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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

    @pytest.mark.unit
    def test_cut_pad_success(self, editor, sample_audio_file):
        """Test cutting a pad to clipboard."""
        pad_index = 5
        editor.assign_sample(pad_index, sample_audio_file)
        editor.set_pad_volume(pad_index, 0.7)
        editor.set_pad_mode(pad_index, PlaybackMode.LOOP)

        result = editor.cut_pad(pad_index)

        # Verify clipboard contains the cut pad
        assert result.sample.name == "test"
        assert result.volume == 0.7
        assert result.mode == PlaybackMode.LOOP

        # Verify source pad is now empty
        source_pad = editor.get_pad(pad_index)
        assert not source_pad.is_assigned

    @pytest.mark.unit
    def test_cut_and_paste(self, editor, sample_audio_file):
        """Test cutting and pasting to another location."""
        editor.assign_sample(0, sample_audio_file)
        editor.set_pad_volume(0, 0.9)

        # Cut from pad 0
        editor.cut_pad(0)

        # Verify pad 0 is empty
        assert not editor.get_pad(0).is_assigned

        # Paste to pad 10
        editor.paste_pad(10)

        # Verify pad 10 has the sample
        target_pad = editor.get_pad(10)
        assert target_pad.sample.name == "test"
        assert target_pad.volume == 0.9

    @pytest.mark.unit
    def test_cut_empty_pad(self, editor):
        """Test that cutting empty pad raises ValueError."""
        with pytest.raises(ValueError, match="Cannot cut empty pad 0"):
            editor.cut_pad(0)

    @pytest.mark.unit
    def test_cut_pad_out_of_range(self, editor):
        """Test that invalid pad index raises IndexError."""
        with pytest.raises(IndexError, match=r"Pad index 64 out of range \(0-63\)"):
            editor.cut_pad(64)


class TestEditorServiceClipboardInspection:
    """Test clipboard inspection methods."""

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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

    @pytest.mark.unit
    def test_has_clipboard_empty(self, editor):
        """Test has_clipboard returns False when empty."""
        assert editor.has_clipboard is False

    @pytest.mark.unit
    def test_has_clipboard_after_copy(self, editor, sample_audio_file):
        """Test has_clipboard returns True after copy."""
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)
        assert editor.has_clipboard is True

    @pytest.mark.unit
    def test_has_clipboard_after_cut(self, editor, sample_audio_file):
        """Test has_clipboard returns True after cut."""
        editor.assign_sample(0, sample_audio_file)
        editor.cut_pad(0)
        assert editor.has_clipboard is True


class TestEditorServiceBulkClear:
    """Test clear_all and clear_range methods."""

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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

    @pytest.mark.unit
    def test_clear_all_empty_launchpad(self, editor):
        """Test clearing all pads when all are empty."""
        count = editor.clear_all()
        assert count == 0

    @pytest.mark.unit
    def test_clear_all_with_samples(self, editor, sample_audio_file):
        """Test clearing all pads with some samples."""
        # Assign samples to a few pads
        editor.assign_sample(0, sample_audio_file)
        editor.assign_sample(5, sample_audio_file)
        editor.assign_sample(10, sample_audio_file)

        count = editor.clear_all()

        # Should have cleared 3 pads
        assert count == 3

        # All pads should be empty
        for i in range(editor.grid_size):
            assert not editor.get_pad(i).is_assigned

    @pytest.mark.unit
    def test_clear_range_success(self, editor, sample_audio_file):
        """Test clearing a range of pads."""
        # Assign samples to pads 0-9
        for i in range(10):
            editor.assign_sample(i, sample_audio_file)

        # Clear pads 3-7
        count = editor.clear_range(3, 7)

        # Should have cleared 5 pads
        assert count == 5

        # Verify pads 0-2 still have samples
        for i in range(3):
            assert editor.get_pad(i).is_assigned

        # Verify pads 3-7 are empty
        for i in range(3, 8):
            assert not editor.get_pad(i).is_assigned

        # Verify pads 8-9 still have samples
        for i in range(8, 10):
            assert editor.get_pad(i).is_assigned

    @pytest.mark.unit
    def test_clear_range_single_pad(self, editor, sample_audio_file):
        """Test clearing a range with single pad."""
        editor.assign_sample(5, sample_audio_file)

        count = editor.clear_range(5, 5)

        assert count == 1
        assert not editor.get_pad(5).is_assigned

    @pytest.mark.unit
    def test_clear_range_start_greater_than_end(self, editor):
        """Test that start > end raises ValueError."""
        with pytest.raises(ValueError, match=r"Start index 10 must be <= end index 5"):
            editor.clear_range(10, 5)

    @pytest.mark.unit
    def test_clear_range_out_of_bounds(self, editor):
        """Test that out of range indices raise IndexError."""
        with pytest.raises(IndexError, match=r"Start pad index 64 out of range"):
            editor.clear_range(64, 70)

        with pytest.raises(IndexError, match=r"End pad index 100 out of range"):
            editor.clear_range(0, 100)

    @pytest.mark.unit
    def test_clear_range_empty_pads(self, editor, sample_audio_file):
        """Test clearing range that includes empty pads."""
        # Only assign to pads 1 and 3
        editor.assign_sample(1, sample_audio_file)
        editor.assign_sample(3, sample_audio_file)

        # Clear range 0-5 (includes empty pads 0, 2, 4, 5)
        count = editor.clear_range(0, 5)

        # Should only count the 2 that had samples
        assert count == 2

        # All should be empty now
        for i in range(6):
            assert not editor.get_pad(i).is_assigned


class TestEditorServiceEvents:
    """Test event notification system."""

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
        service = EditorService(config)
        service.update_launchpad(launchpad)
        return service

    @pytest.fixture
    def observer(self):
        """Create mock observer."""
        return Mock(spec=EditObserver)

    @pytest.mark.unit
    def test_register_observer(self, editor, observer):
        """Test registering an observer."""
        editor.register_observer(observer)
        assert observer in editor._observers

    @pytest.mark.unit
    def test_unregister_observer(self, editor, observer):
        """Test unregistering an observer."""
        editor.register_observer(observer)
        editor.unregister_observer(observer)
        assert observer not in editor._observers

    @pytest.mark.unit
    def test_register_same_observer_twice(self, editor, observer):
        """Test that registering same observer twice is idempotent."""
        editor.register_observer(observer)
        editor.register_observer(observer)
        assert editor._observers.count(observer) == 1

    @pytest.mark.unit
    def test_assign_sample_fires_event(self, editor, observer, sample_audio_file):
        """Test that assign_sample fires PAD_ASSIGNED event."""
        editor.register_observer(observer)
        
        pad = editor.assign_sample(5, sample_audio_file)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_ASSIGNED
        assert indices == [5]
        assert len(pads) == 1
        assert pads[0].is_assigned

    @pytest.mark.unit
    def test_clear_pad_fires_event(self, editor, observer, sample_audio_file):
        """Test that clear_pad fires PAD_CLEARED event."""
        editor.assign_sample(3, sample_audio_file)
        editor.register_observer(observer)
        
        pad = editor.clear_pad(3)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_CLEARED
        assert indices == [3]
        assert len(pads) == 1
        assert not pads[0].is_assigned

    @pytest.mark.unit
    def test_set_pad_mode_fires_event(self, editor, observer, sample_audio_file):
        """Test that set_pad_mode fires PAD_MODE_CHANGED event."""
        editor.assign_sample(7, sample_audio_file)
        editor.register_observer(observer)
        
        pad = editor.set_pad_mode(7, PlaybackMode.LOOP)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_MODE_CHANGED
        assert indices == [7]
        assert pads[0].mode == PlaybackMode.LOOP

    @pytest.mark.unit
    def test_set_pad_volume_fires_event(self, editor, observer, sample_audio_file):
        """Test that set_pad_volume fires PAD_VOLUME_CHANGED event."""
        editor.assign_sample(2, sample_audio_file)
        editor.register_observer(observer)
        
        pad = editor.set_pad_volume(2, 0.5)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_VOLUME_CHANGED
        assert indices == [2]
        assert pads[0].volume == 0.5

    @pytest.mark.unit
    def test_set_sample_name_fires_event(self, editor, observer, sample_audio_file):
        """Test that set_sample_name fires PAD_NAME_CHANGED event."""
        editor.assign_sample(8, sample_audio_file)
        editor.register_observer(observer)
        
        pad = editor.set_sample_name(8, "New Name")
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_NAME_CHANGED
        assert indices == [8]
        assert pads[0].sample.name == "New Name"

    @pytest.mark.unit
    def test_move_pad_fires_event(self, editor, observer, sample_audio_file):
        """Test that move_pad fires PAD_MOVED event with both pads."""
        editor.assign_sample(4, sample_audio_file)
        editor.register_observer(observer)
        
        source_pad, target_pad = editor.move_pad(4, 9, swap=False)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_MOVED
        assert indices == [4, 9]
        assert len(pads) == 2
        assert not pads[0].is_assigned  # Source cleared
        assert pads[1].is_assigned      # Target has sample

    @pytest.mark.unit
    def test_duplicate_pad_fires_event(self, editor, observer, sample_audio_file):
        """Test that duplicate_pad fires PAD_DUPLICATED event."""
        editor.assign_sample(1, sample_audio_file)
        editor.register_observer(observer)
        
        pad = editor.duplicate_pad(1, 6, overwrite=False)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_DUPLICATED
        assert indices == [6]
        assert pads[0].is_assigned

    @pytest.mark.unit
    def test_paste_pad_fires_event(self, editor, observer, sample_audio_file):
        """Test that paste_pad fires PAD_ASSIGNED event."""
        editor.assign_sample(0, sample_audio_file)
        editor.copy_pad(0)
        editor.register_observer(observer)
        
        pad = editor.paste_pad(10, overwrite=False)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_ASSIGNED
        assert indices == [10]
        assert pads[0].is_assigned

    @pytest.mark.unit
    def test_cut_pad_fires_event(self, editor, observer, sample_audio_file):
        """Test that cut_pad fires PAD_CLEARED event for source."""
        editor.assign_sample(15, sample_audio_file)
        editor.register_observer(observer)
        
        clipboard_pad = editor.cut_pad(15)
        
        observer.on_edit_event.assert_called_once()
        event, indices, pads = observer.on_edit_event.call_args[0]
        assert event == EditEvent.PAD_CLEARED
        assert indices == [15]
        assert not pads[0].is_assigned

    # NOTE: test_select_pad_fires_event removed - selection moved to UI layer
    # Selection is now managed by TUI app and fires SelectionEvent instead of EditEvent

    @pytest.mark.unit
    def test_observer_exception_doesnt_break_others(self, editor, sample_audio_file):
        """Test that exception in one observer doesn't break others."""
        bad_observer = Mock(spec=EditObserver)
        bad_observer.on_edit_event.side_effect = RuntimeError("Bad observer")
        
        good_observer = Mock(spec=EditObserver)
        
        editor.register_observer(bad_observer)
        editor.register_observer(good_observer)
        
        # Should not raise despite bad_observer failing
        editor.assign_sample(0, sample_audio_file)
        
        # Both observers should have been called
        bad_observer.on_edit_event.assert_called_once()
        good_observer.on_edit_event.assert_called_once()

    @pytest.mark.unit
    def test_multiple_observers_all_notified(self, editor, sample_audio_file):
        """Test that all registered observers receive events."""
        observer1 = Mock(spec=EditObserver)
        observer2 = Mock(spec=EditObserver)
        observer3 = Mock(spec=EditObserver)
        
        editor.register_observer(observer1)
        editor.register_observer(observer2)
        editor.register_observer(observer3)
        
        editor.assign_sample(12, sample_audio_file)
        
        observer1.on_edit_event.assert_called_once()
        observer2.on_edit_event.assert_called_once()
        observer3.on_edit_event.assert_called_once()

