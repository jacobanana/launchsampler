"""Tests for persistence safety features (backups, atomic writes, corruption handling)."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from launchsampler.exceptions import ConfigurationError
from launchsampler.model_manager.persistence import PydanticPersistence


class SampleModel(BaseModel):
    """Simple model for testing."""

    name: str = "test"
    value: int = 42


class TestPersistenceSafety:
    """Test safety features of PydanticPersistence."""

    def test_save_creates_backup(self, tmp_path: Path):
        """Test that save_json creates a .bak file before overwriting."""
        config_path = tmp_path / "config.json"

        # Create initial file
        initial = SampleModel(name="original", value=1)
        PydanticPersistence.save_json(initial, config_path, backup=False)

        # Modify and save again (with backup enabled)
        modified = SampleModel(name="modified", value=2)
        PydanticPersistence.save_json(modified, config_path, backup=True)

        # Verify backup exists with original content
        backup_path = config_path.with_suffix(".json.bak")
        assert backup_path.exists()

        backup_data = PydanticPersistence.load_json(backup_path, SampleModel)
        assert backup_data.name == "original"
        assert backup_data.value == 1

        # Verify main file has new content
        current_data = PydanticPersistence.load_json(config_path, SampleModel)
        assert current_data.name == "modified"
        assert current_data.value == 2

    def test_save_without_backup(self, tmp_path: Path):
        """Test that backup can be disabled."""
        config_path = tmp_path / "config.json"

        # Create initial file
        initial = SampleModel(name="original", value=1)
        PydanticPersistence.save_json(initial, config_path, backup=False)

        # Save again with backup=False
        modified = SampleModel(name="modified", value=2)
        PydanticPersistence.save_json(modified, config_path, backup=False)

        # Verify no backup was created
        backup_path = config_path.with_suffix(".json.bak")
        assert not backup_path.exists()

    def test_atomic_write_cleans_up_temp_file(self, tmp_path: Path):
        """Test that temporary file is cleaned up after successful write."""
        config_path = tmp_path / "config.json"
        temp_path = config_path.with_suffix(".json.tmp")

        # Save data
        data = SampleModel(name="test", value=123)
        PydanticPersistence.save_json(data, config_path)

        # Verify temp file doesn't exist
        assert not temp_path.exists()

        # Verify data was written correctly
        loaded = PydanticPersistence.load_json(config_path, SampleModel)
        assert loaded.name == "test"
        assert loaded.value == 123

    def test_ensure_valid_or_create_missing_file(self, tmp_path: Path):
        """Test that missing file triggers default creation and save."""
        config_path = tmp_path / "missing.json"

        # Ensure file doesn't exist
        assert not config_path.exists()

        # Load or create with auto_save=True
        result = PydanticPersistence.ensure_valid_or_create(
            config_path, SampleModel, auto_save=True
        )

        # Verify default values
        assert result.name == "test"
        assert result.value == 42

        # Verify file was created
        assert config_path.exists()

        # Verify no backup was created (file didn't exist before)
        backup_path = config_path.with_suffix(".json.bak")
        assert not backup_path.exists()

    def test_ensure_valid_or_create_corrupted_file_not_overwritten(self, tmp_path: Path):
        """Test that corrupted file is NOT overwritten by ensure_valid_or_create."""
        config_path = tmp_path / "corrupted.json"

        # Create corrupted file
        config_path.write_text("{ invalid json }", encoding="utf-8")
        original_content = config_path.read_text()

        # Try to load or create
        result = PydanticPersistence.ensure_valid_or_create(
            config_path,
            SampleModel,
            auto_save=True,  # This should NOT overwrite corrupted file
        )

        # Verify we got default values
        assert result.name == "test"
        assert result.value == 42

        # Verify corrupted file was NOT overwritten
        assert config_path.read_text() == original_content

    def test_ensure_valid_or_create_invalid_schema_not_overwritten(self, tmp_path: Path):
        """Test that file with schema mismatch is NOT overwritten."""
        config_path = tmp_path / "invalid_schema.json"

        # Create file with wrong schema
        wrong_data = {"wrong_field": "value", "another_field": 123}
        config_path.write_text(json.dumps(wrong_data), encoding="utf-8")
        original_content = config_path.read_text()

        # Try to load or create
        result = PydanticPersistence.ensure_valid_or_create(
            config_path, SampleModel, auto_save=True
        )

        # Verify we got default values
        assert result.name == "test"
        assert result.value == 42

        # Verify invalid file was NOT overwritten
        assert config_path.read_text() == original_content

    def test_ensure_valid_or_create_with_default_factory(self, tmp_path: Path):
        """Test custom default factory."""
        config_path = tmp_path / "custom.json"

        # Use custom default factory
        result = PydanticPersistence.ensure_valid_or_create(
            config_path,
            SampleModel,
            default_factory=lambda: SampleModel(name="custom", value=999),
            auto_save=True,
        )

        # Verify custom defaults were used
        assert result.name == "custom"
        assert result.value == 999

        # Verify file was saved
        loaded = PydanticPersistence.load_json(config_path, SampleModel)
        assert loaded.name == "custom"
        assert loaded.value == 999

    def test_ensure_valid_or_create_no_auto_save(self, tmp_path: Path):
        """Test that auto_save=False prevents file creation."""
        config_path = tmp_path / "nosave.json"

        # Load or create with auto_save=False
        result = PydanticPersistence.ensure_valid_or_create(
            config_path, SampleModel, auto_save=False
        )

        # Verify we got defaults
        assert result.name == "test"
        assert result.value == 42

        # Verify file was NOT created
        assert not config_path.exists()

    def test_load_json_or_default_missing_file(self, tmp_path: Path):
        """Test load_json_or_default with missing file."""
        config_path = tmp_path / "missing.json"

        result = PydanticPersistence.load_json_or_default(config_path, SampleModel)

        # Should return default values
        assert result.name == "test"
        assert result.value == 42

        # Should NOT create file
        assert not config_path.exists()

    def test_load_json_or_default_corrupted_file_raises(self, tmp_path: Path):
        """Test that load_json_or_default raises on corrupted files."""
        config_path = tmp_path / "corrupted.json"
        config_path.write_text("{ invalid }", encoding="utf-8")

        # Corrupted files should raise ConfigurationError
        with pytest.raises(ConfigurationError):
            PydanticPersistence.load_json_or_default(config_path, SampleModel)

    def test_backup_preserves_file_metadata(self, tmp_path: Path):
        """Test that backup preserves file metadata (timestamps, permissions)."""
        config_path = tmp_path / "config.json"

        # Create initial file
        initial = SampleModel(name="original", value=1)
        PydanticPersistence.save_json(initial, config_path, backup=False)

        # Get original modification time
        import time

        time.sleep(0.01)  # Ensure different timestamp

        # Save with backup
        modified = SampleModel(name="modified", value=2)
        PydanticPersistence.save_json(modified, config_path, backup=True)

        # Verify backup exists
        backup_path = config_path.with_suffix(".json.bak")
        assert backup_path.exists()

        # Verify backup has correct content
        backup_data = PydanticPersistence.load_json(backup_path, SampleModel)
        assert backup_data.name == "original"
