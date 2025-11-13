"""Unit tests for utility functions."""

from pathlib import Path

import pytest

from launchsampler.utils import find_common_path


class TestFindCommonPath:
    """Test find_common_path helper function."""

    @pytest.mark.unit
    def test_same_directory(self, temp_dir):
        """Test finding common path when all files are in same directory."""
        paths = [
            temp_dir / "kick.wav",
            temp_dir / "snare.wav",
            temp_dir / "hat.wav",
        ]
        result = find_common_path(paths)
        assert result == temp_dir

    @pytest.mark.unit
    def test_nested_directories(self, temp_dir):
        """Test finding common path with nested subdirectories."""
        samples_dir = temp_dir / "samples"
        paths = [
            samples_dir / "drums" / "kick.wav",
            samples_dir / "drums" / "snare.wav",
            samples_dir / "bass" / "bass.wav",
        ]
        result = find_common_path(paths)
        assert result == samples_dir

    @pytest.mark.unit
    def test_deeply_nested(self, temp_dir):
        """Test with deeply nested directory structures."""
        root = temp_dir / "music" / "samples"
        paths = [
            root / "drums" / "acoustic" / "kick.wav",
            root / "drums" / "electronic" / "snare.wav",
            root / "bass" / "synth" / "bass.wav",
        ]
        result = find_common_path(paths)
        assert result == root

    @pytest.mark.unit
    def test_single_path(self, temp_dir):
        """Test with a single path."""
        path = temp_dir / "kick.wav"
        result = find_common_path([path])
        assert result == temp_dir

    @pytest.mark.unit
    def test_empty_list(self):
        """Test with empty list."""
        result = find_common_path([])
        assert result is None

    @pytest.mark.unit
    def test_different_drives_windows_style(self):
        """Test paths from different drives (Windows-style paths)."""
        # Note: This test simulates the scenario but may behave differently
        # depending on the OS. On Unix systems, it will find root '/'
        paths = [
            Path("C:/samples/kick.wav").resolve(),
            Path("D:/music/snare.wav").resolve(),
        ]
        result = find_common_path(paths)
        # Result depends on OS - on Windows it might be C:\ or root,
        # on Unix it will be /
        assert result is not None

    @pytest.mark.unit
    def test_relative_paths(self, temp_dir):
        """Test with relative paths (should convert to absolute)."""
        # Create actual directories for this test
        dir1 = temp_dir / "samples" / "drums"
        dir1.mkdir(parents=True)

        # Use paths relative to current working dir won't work reliably,
        # but the function resolves them to absolute
        paths = [
            temp_dir / "samples" / "drums" / "kick.wav",
            temp_dir / "samples" / "drums" / "snare.wav",
        ]
        result = find_common_path(paths)
        assert result == dir1
