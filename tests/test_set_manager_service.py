"""Unit tests for SetManagerService."""

import pytest

from launchsampler.models import AppConfig, AudioSample, Launchpad, PlaybackMode, Set
from launchsampler.services import SetManagerService


class TestSetManagerServiceLoad:
    """Test opening sets from files and creating from directories."""

    @pytest.fixture
    def config(self, temp_dir):
        """Create test config."""
        return AppConfig(sets_dir=temp_dir)

    @pytest.fixture
    def service(self, config):
        """Create SetManagerService."""
        return SetManagerService(config)

    @pytest.mark.unit
    def test_open_set_success(self, service, temp_dir, sample_audio_file):
        """Test successfully opening a set from file."""
        # Create a test set
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = AudioSample.from_file(sample_audio_file)
        launchpad.pads[0].mode = PlaybackMode.ONE_SHOT
        test_set = Set(name="test", launchpad=launchpad)

        # Save it using the service
        set_path = temp_dir / "test.json"
        service.save_set(test_set, set_path)

        # Open it back
        loaded = service.open_set(set_path)

        assert loaded.name == "test"
        assert loaded.launchpad.pads[0].is_assigned
        assert loaded.launchpad.pads[0].sample.name == sample_audio_file.stem

    @pytest.mark.unit
    def test_open_set_not_found(self, service, temp_dir):
        """Test opening non-existent file raises error."""
        with pytest.raises(FileNotFoundError, match="Set file not found"):
            service.open_set(temp_dir / "nonexistent.json")

    @pytest.mark.unit
    def test_open_set_by_name_success(self, service, temp_dir, sample_audio_file):
        """Test opening by name from sets directory."""
        # Create a test set in sets_dir
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = AudioSample.from_file(sample_audio_file)
        test_set = Set(name="myset", launchpad=launchpad)

        set_path = temp_dir / "myset.json"
        service.save_set(test_set, set_path)

        # Open by name
        loaded = service.open_set_by_name("myset")

        assert loaded is not None
        assert loaded.name == "myset"
        assert loaded.launchpad.pads[0].is_assigned

    @pytest.mark.unit
    def test_open_set_by_name_not_found(self, service):
        """Test opening non-existent set by name returns None."""
        loaded = service.open_set_by_name("nonexistent")
        assert loaded is None

    @pytest.mark.unit
    def test_create_from_directory_success(self, service, temp_dir, sample_audio_file):
        """Test creating set from samples directory."""
        # Create a directory with a sample
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # Copy sample to directory
        import shutil

        shutil.copy2(sample_audio_file, samples_dir / sample_audio_file.name)

        # Create from directory
        loaded = service.create_from_directory(samples_dir, "test_set")

        assert loaded.name == "test_set"
        assert loaded.samples_root == samples_dir
        assert len(loaded.launchpad.assigned_pads) > 0

    @pytest.mark.unit
    def test_create_from_directory_invalid_path(self, service, temp_dir):
        """Test creating from invalid directory raises error."""
        with pytest.raises(ValueError, match="Invalid samples directory"):
            service.create_from_directory(temp_dir / "nonexistent")

    @pytest.mark.unit
    def test_create_from_directory_default_name(self, service, temp_dir, sample_audio_file):
        """Test directory name used as default set name."""
        samples_dir = temp_dir / "my_samples"
        samples_dir.mkdir()

        import shutil

        shutil.copy2(sample_audio_file, samples_dir / sample_audio_file.name)

        loaded = service.create_from_directory(samples_dir)

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
    def test_save_set_success(self, service, temp_dir, sample_audio_file):
        """Test successfully saving a set to file."""
        # Create a set
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = AudioSample.from_file(sample_audio_file)
        launchpad.pads[0].mode = PlaybackMode.LOOP
        test_set = Set(name="myset", launchpad=launchpad)

        # Save it
        save_path = temp_dir / "output.json"
        service.save_set(test_set, save_path)

        # Verify file exists
        assert save_path.exists()

        # Load it back to verify
        loaded = service.open_set(save_path)
        assert loaded.name == "myset"
        assert loaded.launchpad.pads[0].is_assigned

    @pytest.mark.unit
    def test_save_set_creates_parent_dirs(self, service, temp_dir, sample_audio_file):
        """Test saving creates parent directories if needed."""
        launchpad = Launchpad.create_empty()
        test_set = Set(name="test", launchpad=launchpad)

        # Save to nested path
        save_path = temp_dir / "subdir" / "nested" / "test.json"
        service.save_set(test_set, save_path)

        assert save_path.exists()

    @pytest.mark.unit
    def test_save_set_to_library_success(self, service, temp_dir, sample_audio_file):
        """Test saving to sets library."""
        launchpad = Launchpad.create_empty()
        launchpad.pads[0].sample = AudioSample.from_file(sample_audio_file)
        test_set = Set(name="myset", launchpad=launchpad)

        # Save to sets library
        saved_set, saved_path = service.save_set_to_library(test_set)

        assert saved_path == temp_dir / "myset.json"
        assert saved_path.exists()
        assert saved_set.name == "myset"

    @pytest.mark.unit
    def test_save_set_to_library_custom_filename(self, service, temp_dir):
        """Test saving with custom filename."""
        launchpad = Launchpad.create_empty()
        test_set = Set(name="original", launchpad=launchpad)

        # Save with different filename
        saved_set, saved_path = service.save_set_to_library(test_set, filename="custom")

        assert saved_path == temp_dir / "custom.json"
        assert saved_path.exists()
        assert saved_set.name == "original"

        # Verify set name in file is still "original"
        loaded = service.open_set(saved_path)
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
    def test_create_empty_default_name(self, service):
        """Test creating empty set with default name."""
        empty = service.create_empty()

        assert empty.name == "Untitled"
        assert len(empty.launchpad.assigned_pads) == 0

    @pytest.mark.unit
    def test_create_empty_custom_name(self, service):
        """Test creating empty set with custom name."""
        empty = service.create_empty("MySet")

        assert empty.name == "MySet"
        assert len(empty.launchpad.assigned_pads) == 0
