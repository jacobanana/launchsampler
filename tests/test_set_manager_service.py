"""Unit tests for SetManagerService."""

from pathlib import Path

import pytest

from launchsampler.models import AppConfig, Launchpad, Set, Sample, PlaybackMode
from launchsampler.services import SetManagerService


class TestSetManagerServiceLoad:
    """Test loading sets from files and directories."""

    @pytest.fixture
    def config(self, temp_dir):
        """Create test config."""
        return AppConfig(sets_dir=temp_dir)

    @pytest.fixture
    def service(self, config):
        """Create SetManagerService."""
        return SetManagerService(config)

    @pytest.mark.unit
    def test_load_from_file_success(self, service, temp_dir, sample_audio_file):
        """Test successfully loading a set from file."""
        # Create a test set
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = Sample.from_file(sample_audio_file)
        launchpad.pads[0].mode = PlaybackMode.ONE_SHOT
        test_set = Set(name="test", launchpad=launchpad)

        # Save it
        set_path = temp_dir / "test.json"
        test_set.save_to_file(set_path)

        # Load it back
        loaded = service.load_from_file(set_path)

        assert loaded.name == "test"
        assert loaded.launchpad.pads[0].is_assigned
        assert loaded.launchpad.pads[0].sample.name == sample_audio_file.stem

    @pytest.mark.unit
    def test_load_from_file_not_found(self, service, temp_dir):
        """Test loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError, match="Set file not found"):
            service.load_from_file(temp_dir / "nonexistent.json")

    @pytest.mark.unit
    def test_load_from_file_by_name_success(self, service, temp_dir, sample_audio_file):
        """Test loading by name from sets directory."""
        # Create a test set in sets_dir
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = Sample.from_file(sample_audio_file)
        test_set = Set(name="myset", launchpad=launchpad)

        set_path = temp_dir / "myset.json"
        test_set.save_to_file(set_path)

        # Load by name
        loaded = service.load_from_file_by_name("myset")

        assert loaded is not None
        assert loaded.name == "myset"
        assert loaded.launchpad.pads[0].is_assigned

    @pytest.mark.unit
    def test_load_from_file_by_name_not_found(self, service):
        """Test loading non-existent set by name returns None."""
        loaded = service.load_from_file_by_name("nonexistent")
        assert loaded is None

    @pytest.mark.unit
    def test_load_from_directory_success(self, service, temp_dir, sample_audio_file):
        """Test loading samples from directory."""
        # Create a directory with a sample
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # Copy sample to directory
        import shutil
        shutil.copy2(sample_audio_file, samples_dir / sample_audio_file.name)

        # Load from directory
        loaded = service.load_from_directory(samples_dir, "test_set")

        assert loaded.name == "test_set"
        assert loaded.samples_root == samples_dir
        assert len(loaded.launchpad.assigned_pads) > 0

    @pytest.mark.unit
    def test_load_from_directory_invalid_path(self, service, temp_dir):
        """Test loading from invalid directory raises error."""
        with pytest.raises(ValueError, match="Invalid samples directory"):
            service.load_from_directory(temp_dir / "nonexistent")

    @pytest.mark.unit
    def test_load_from_directory_default_name(self, service, temp_dir, sample_audio_file):
        """Test directory name used as default set name."""
        samples_dir = temp_dir / "my_samples"
        samples_dir.mkdir()

        import shutil
        shutil.copy2(sample_audio_file, samples_dir / sample_audio_file.name)

        loaded = service.load_from_directory(samples_dir)

        assert loaded.name == "my_samples"


class TestSetManagerServiceSave:
    """Test saving sets to files."""

    @pytest.fixture
    def config(self, temp_dir):
        """Create test config."""
        return AppConfig(sets_dir=temp_dir)

    @pytest.fixture
    def service(self, config):
        """Create SetManagerService."""
        return SetManagerService(config)

    @pytest.mark.unit
    def test_save_to_file_success(self, service, temp_dir, sample_audio_file):
        """Test successfully saving a set to file."""
        # Create a set
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = Sample.from_file(sample_audio_file)
        launchpad.pads[0].mode = PlaybackMode.LOOP
        test_set = Set(name="myset", launchpad=launchpad)

        # Save it
        save_path = temp_dir / "output.json"
        service.save_to_file(test_set, save_path)

        # Verify file exists
        assert save_path.exists()

        # Load it back to verify
        loaded = Set.load_from_file(save_path)
        assert loaded.name == "myset"
        assert loaded.launchpad.pads[0].is_assigned

    @pytest.mark.unit
    def test_save_to_file_creates_parent_dirs(self, service, temp_dir, sample_audio_file):
        """Test saving creates parent directories if needed."""
        launchpad = Launchpad.create_empty()
        test_set = Set(name="test", launchpad=launchpad)

        # Save to nested path
        save_path = temp_dir / "subdir" / "nested" / "test.json"
        service.save_to_file(test_set, save_path)

        assert save_path.exists()

    @pytest.mark.unit
    def test_save_to_sets_directory_success(self, service, temp_dir, sample_audio_file):
        """Test saving to sets directory."""
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = Sample.from_file(sample_audio_file)
        test_set = Set(name="myset", launchpad=launchpad)

        # Save to sets directory
        saved_path = service.save_to_sets_directory(test_set)

        assert saved_path == temp_dir / "myset.json"
        assert saved_path.exists()

    @pytest.mark.unit
    def test_save_to_sets_directory_custom_filename(self, service, temp_dir):
        """Test saving with custom filename."""
        launchpad = Launchpad.create_empty()
        test_set = Set(name="original", launchpad=launchpad)

        # Save with different filename
        saved_path = service.save_to_sets_directory(test_set, filename="custom")

        assert saved_path == temp_dir / "custom.json"
        assert saved_path.exists()

        # Verify set name in file is still "original"
        loaded = Set.load_from_file(saved_path)
        assert loaded.name == "original"


class TestSetManagerServiceCreate:
    """Test creating empty sets."""

    @pytest.fixture
    def config(self, temp_dir):
        """Create test config."""
        return AppConfig(sets_dir=temp_dir)

    @pytest.fixture
    def service(self, config):
        """Create SetManagerService."""
        return SetManagerService(config)

    @pytest.mark.unit
    def test_create_empty_set_default_name(self, service):
        """Test creating empty set with default name."""
        empty = service.create_empty_set()

        assert empty.name == "Untitled"
        assert len(empty.launchpad.assigned_pads) == 0

    @pytest.mark.unit
    def test_create_empty_set_custom_name(self, service):
        """Test creating empty set with custom name."""
        empty = service.create_empty_set("MySet")

        assert empty.name == "MySet"
        assert len(empty.launchpad.assigned_pads) == 0
