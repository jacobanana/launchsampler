"""Unit tests for ModelManagerService."""

from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field, ValidationError

from launchsampler.model_manager import ModelEvent, ModelManagerService, ModelObserver
from launchsampler.models import AppConfig


# Test configuration model (renamed to avoid pytest collection warning)
class SampleConfig(BaseModel):
    """Simple config model for testing."""

    string_field: str = "default_string"
    int_field: int = 42
    float_field: float = 3.14
    bool_field: bool = True
    optional_field: str | None = None
    path_field: Path = Field(default_factory=lambda: Path("/tmp/test"))


class TestModelManagerServiceBasics:
    """Test basic ModelManagerService functionality."""

    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return SampleConfig()

    @pytest.fixture
    def service(self, config):
        """Create a ModelManagerService instance."""
        return ModelManagerService[SampleConfig](SampleConfig, config)

    @pytest.mark.unit
    def test_initialization(self, service):
        """Test service initializes correctly."""
        assert service._model_type == SampleConfig
        assert service._model is not None
        assert service._default_path is None

    @pytest.mark.unit
    def test_initialization_with_default_path(self, config, temp_dir):
        """Test service initializes with default path."""
        default_path = temp_dir / "config.json"
        service = ModelManagerService[SampleConfig](SampleConfig, config, default_path)
        assert service._default_path == default_path

    @pytest.mark.unit
    def test_get_existing_field(self, service):
        """Test getting an existing configuration field."""
        assert service.get("string_field") == "default_string"
        assert service.get("int_field") == 42
        assert service.get("bool_field") is True

    @pytest.mark.unit
    def test_get_nonexistent_field_with_default(self, service):
        """Test getting a nonexistent field returns default."""
        assert service.get("nonexistent", "fallback") == "fallback"
        assert service.get("nonexistent", None) is None
        assert service.get("nonexistent", 123) == 123

    @pytest.mark.unit
    def test_get_all(self, service):
        """Test getting all config values."""
        all_config = service.get_all()
        assert isinstance(all_config, dict)
        assert all_config["string_field"] == "default_string"
        assert all_config["int_field"] == 42
        assert all_config["bool_field"] is True
        assert "path_field" in all_config

    @pytest.mark.unit
    def test_get_model(self, service):
        """Test getting a copy of the config object."""
        config_copy = service.get_model()
        assert isinstance(config_copy, SampleConfig)
        assert config_copy.string_field == "default_string"

        # Verify it's a deep copy
        config_copy.string_field = "modified"
        assert service.get("string_field") == "default_string"


class TestModelManagerServiceMutation:
    """Test ModelManagerService mutation operations."""

    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return SampleConfig()

    @pytest.fixture
    def service(self, config):
        """Create a ModelManagerService instance."""
        return ModelManagerService[SampleConfig](SampleConfig, config)

    @pytest.fixture
    def mock_observer(self):
        """Create a mock observer."""
        observer = Mock(spec=ModelObserver)
        return observer

    @pytest.mark.unit
    def test_set_field(self, service, mock_observer):
        """Test setting a configuration field."""
        service.register_observer(mock_observer)
        service.set("string_field", "new_value")

        assert service.get("string_field") == "new_value"

        # Verify observer was notified
        mock_observer.on_model_event.assert_called_once()
        call_args = mock_observer.on_model_event.call_args
        assert call_args[0][0] == ModelEvent.MODEL_UPDATED
        assert call_args[1]["keys"] == ["string_field"]
        assert call_args[1]["values"] == {"string_field": "new_value"}

    @pytest.mark.unit
    def test_set_multiple_fields(self, service):
        """Test setting multiple different fields."""
        service.set("string_field", "changed")
        service.set("int_field", 999)
        service.set("bool_field", False)

        assert service.get("string_field") == "changed"
        assert service.get("int_field") == 999
        assert service.get("bool_field") is False

    @pytest.mark.unit
    def test_set_nonexistent_field_raises_error(self, service):
        """Test setting a nonexistent field raises AttributeError."""
        with pytest.raises(AttributeError, match="has no field 'nonexistent'"):
            service.set("nonexistent", "value")

    @pytest.mark.unit
    def test_set_invalid_type_raises_validation_error(self, service):
        """Test setting an invalid type raises ValidationError."""
        with pytest.raises(ValidationError):
            service.set("int_field", "not_an_int")

    @pytest.mark.unit
    def test_update_batch(self, service, mock_observer):
        """Test batch updating multiple fields."""
        service.register_observer(mock_observer)

        updates = {"string_field": "batch_updated", "int_field": 777, "bool_field": False}
        service.update(updates)

        assert service.get("string_field") == "batch_updated"
        assert service.get("int_field") == 777
        assert service.get("bool_field") is False

        # Verify single notification with all updates
        mock_observer.on_model_event.assert_called_once()
        call_args = mock_observer.on_model_event.call_args
        assert call_args[0][0] == ModelEvent.MODEL_UPDATED
        assert set(call_args[1]["keys"]) == {"string_field", "int_field", "bool_field"}
        assert call_args[1]["values"] == updates

    @pytest.mark.unit
    def test_update_with_nonexistent_field_raises_error(self, service):
        """Test batch update with nonexistent field raises AttributeError."""
        with pytest.raises(AttributeError, match="has no field 'nonexistent'"):
            service.update({"string_field": "valid", "nonexistent": "invalid"})

        # Verify no changes were applied (atomic failure)
        assert service.get("string_field") == "default_string"

    @pytest.mark.unit
    def test_reset(self, service, mock_observer):
        """Test resetting config to defaults."""
        service.register_observer(mock_observer)

        # Modify some fields
        service.set("string_field", "modified")
        service.set("int_field", 999)
        mock_observer.reset_mock()

        # Reset to defaults
        service.reset()

        assert service.get("string_field") == "default_string"
        assert service.get("int_field") == 42
        assert service.get("bool_field") is True

        # Verify observer was notified
        mock_observer.on_model_event.assert_called_once()
        call_args = mock_observer.on_model_event.call_args
        assert call_args[0][0] == ModelEvent.MODEL_RESET
        assert "model" in call_args[1]


class TestModelManagerServicePersistence:
    """Test ModelManagerService persistence operations."""

    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return SampleConfig(string_field="test_value", int_field=123)

    @pytest.fixture
    def service(self, config, temp_dir):
        """Create a ModelManagerService instance with default path."""
        default_path = temp_dir / "config.json"
        return ModelManagerService[SampleConfig](SampleConfig, config, default_path)

    @pytest.fixture
    def mock_observer(self):
        """Create a mock observer."""
        return Mock(spec=ModelObserver)

    @pytest.mark.unit
    def test_save_with_default_path(self, service, temp_dir, mock_observer):
        """Test saving config to default path."""
        service.register_observer(mock_observer)
        service.save()

        config_path = temp_dir / "config.json"
        assert config_path.exists()

        # Verify observer was notified
        mock_observer.on_model_event.assert_called_once()
        call_args = mock_observer.on_model_event.call_args
        assert call_args[0][0] == ModelEvent.MODEL_SAVED
        assert call_args[1]["path"] == config_path

    @pytest.mark.unit
    def test_save_with_explicit_path(self, service, temp_dir, mock_observer):
        """Test saving config to explicit path."""
        service.register_observer(mock_observer)
        custom_path = temp_dir / "custom_config.json"
        service.save(custom_path)

        assert custom_path.exists()

        # Verify observer was notified with correct path
        call_args = mock_observer.on_model_event.call_args
        assert call_args[1]["path"] == custom_path

    @pytest.mark.unit
    def test_save_without_path_raises_error(self, config):
        """Test saving without path raises ValueError."""
        service = ModelManagerService[SampleConfig](SampleConfig, config)  # No default path
        with pytest.raises(ValueError, match="No path specified"):
            service.save()

    @pytest.mark.unit
    def test_load_with_default_path(self, service, temp_dir, mock_observer):
        """Test loading config from default path."""
        # Save first
        service.set("string_field", "saved_value")
        service.set("int_field", 999)
        service.save()

        # Create new service and load
        new_config = SampleConfig()
        new_service = ModelManagerService[SampleConfig](
            SampleConfig, new_config, temp_dir / "config.json"
        )
        new_service.register_observer(mock_observer)
        new_service.load()

        assert new_service.get("string_field") == "saved_value"
        assert new_service.get("int_field") == 999

        # Verify observer was notified
        mock_observer.on_model_event.assert_called_once()
        call_args = mock_observer.on_model_event.call_args
        assert call_args[0][0] == ModelEvent.MODEL_LOADED

    @pytest.mark.unit
    def test_load_with_explicit_path(self, service, temp_dir):
        """Test loading config from explicit path."""
        custom_path = temp_dir / "custom_config.json"
        service.set("string_field", "custom_saved")
        service.save(custom_path)

        # Load from custom path
        new_config = SampleConfig()
        new_service = ModelManagerService[SampleConfig](SampleConfig, new_config)
        new_service.load(custom_path)

        assert new_service.get("string_field") == "custom_saved"

    @pytest.mark.unit
    def test_load_without_path_raises_error(self, config):
        """Test loading without path raises ValueError."""
        service = ModelManagerService[SampleConfig](SampleConfig, config)  # No default path
        with pytest.raises(ValueError, match="No path specified"):
            service.load()

    @pytest.mark.unit
    def test_load_nonexistent_file_raises_error(self, service, temp_dir):
        """Test loading from nonexistent file raises FileNotFoundError."""
        nonexistent_path = temp_dir / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            service.load(nonexistent_path)

    @pytest.mark.unit
    def test_reload(self, service):
        """Test reload convenience method."""
        # Save initial state
        service.set("string_field", "saved_state")
        service.save()

        # Modify in memory
        service.set("string_field", "modified_state")
        assert service.get("string_field") == "modified_state"

        # Reload from disk
        service.reload()
        assert service.get("string_field") == "saved_state"

    @pytest.mark.unit
    def test_save_creates_parent_directories(self, config, temp_dir):
        """Test save creates parent directories if they don't exist."""
        nested_path = temp_dir / "nested" / "dir" / "config.json"
        service = ModelManagerService[SampleConfig](SampleConfig, config, nested_path)
        service.save()

        assert nested_path.exists()
        assert nested_path.parent.is_dir()


class TestModelManagerServiceObservers:
    """Test ModelManagerService observer functionality."""

    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return SampleConfig()

    @pytest.fixture
    def service(self, config):
        """Create a ModelManagerService instance."""
        return ModelManagerService[SampleConfig](SampleConfig, config)

    @pytest.mark.unit
    def test_register_observer(self, service):
        """Test registering an observer."""
        observer = Mock(spec=ModelObserver)
        service.register_observer(observer)
        # Should not raise

    @pytest.mark.unit
    def test_unregister_observer(self, service):
        """Test unregistering an observer."""
        observer = Mock(spec=ModelObserver)
        service.register_observer(observer)
        service.unregister_observer(observer)

        # Should not be notified after unregistration
        service.set("string_field", "test")
        observer.on_model_event.assert_not_called()

    @pytest.mark.unit
    def test_multiple_observers(self, service):
        """Test multiple observers receive notifications."""
        observer1 = Mock(spec=ModelObserver)
        observer2 = Mock(spec=ModelObserver)
        observer3 = Mock(spec=ModelObserver)

        service.register_observer(observer1)
        service.register_observer(observer2)
        service.register_observer(observer3)

        service.set("string_field", "broadcast")

        observer1.on_model_event.assert_called_once()
        observer2.on_model_event.assert_called_once()
        observer3.on_model_event.assert_called_once()

    @pytest.mark.unit
    def test_observer_exception_does_not_propagate(self, service):
        """Test that observer exceptions are caught and don't propagate."""
        failing_observer = Mock(spec=ModelObserver)
        failing_observer.on_model_event.side_effect = Exception("Observer failed")

        working_observer = Mock(spec=ModelObserver)

        service.register_observer(failing_observer)
        service.register_observer(working_observer)

        # Should not raise despite failing observer
        service.set("string_field", "test")

        # Both observers should have been called
        failing_observer.on_model_event.assert_called_once()
        working_observer.on_model_event.assert_called_once()


class TestModelManagerServiceThreadSafety:
    """Test ModelManagerService thread safety."""

    @pytest.fixture
    def config(self):
        """Create a test config instance."""
        return SampleConfig()

    @pytest.fixture
    def service(self, config):
        """Create a ModelManagerService instance."""
        return ModelManagerService[SampleConfig](SampleConfig, config)

    @pytest.mark.unit
    def test_concurrent_reads(self, service):
        """Test concurrent reads are safe."""
        results = []

        def read_config():
            for _ in range(100):
                results.append(service.get("int_field"))

        threads = [Thread(target=read_config) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should return the default value
        assert all(r == 42 for r in results)

    @pytest.mark.unit
    def test_concurrent_writes(self, service):
        """Test concurrent writes are safe (no data corruption)."""

        def write_config(value):
            for _ in range(50):
                service.set("int_field", value)

        threads = [Thread(target=write_config, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final value should be one of the written values (0-9)
        final_value = service.get("int_field")
        assert 0 <= final_value < 10

    @pytest.mark.unit
    def test_concurrent_read_write(self, service):
        """Test concurrent reads and writes are safe."""
        read_results = []

        def reader():
            for _ in range(100):
                read_results.append(service.get("int_field"))

        def writer(value):
            for _ in range(50):
                service.set("int_field", value)

        threads = [Thread(target=reader) for _ in range(5)] + [
            Thread(target=writer, args=(i,)) for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors (no assertions on values due to race conditions)
        assert len(read_results) == 500  # 5 readers * 100 reads each


class TestModelManagerServiceWithAppConfig:
    """Test ModelManagerService with real AppConfig model."""

    @pytest.fixture
    def app_config(self, temp_dir):
        """Create an AppConfig instance."""
        return AppConfig(sets_dir=temp_dir / "sets")

    @pytest.fixture
    def service(self, app_config, temp_dir):
        """Create a ModelManagerService for AppConfig."""
        return ModelManagerService[AppConfig](AppConfig, app_config, temp_dir / "app_config.json")

    @pytest.mark.unit
    def test_get_appconfig_fields(self, service):
        """Test getting AppConfig fields."""
        assert isinstance(service.get("sets_dir"), Path)
        assert service.get("default_buffer_size") == 512
        assert service.get("auto_save") is True
        assert service.get("midi_poll_interval") == 2.0

    @pytest.mark.unit
    def test_set_appconfig_fields(self, service):
        """Test setting AppConfig fields."""
        service.set("auto_save", False)
        service.set("default_buffer_size", 1024)
        service.set("midi_poll_interval", 5.0)

        assert service.get("auto_save") is False
        assert service.get("default_buffer_size") == 1024
        assert service.get("midi_poll_interval") == 5.0

    @pytest.mark.unit
    def test_save_load_appconfig(self, service):
        """Test saving and loading AppConfig."""
        service.set("auto_save", False)
        service.set("default_buffer_size", 2048)
        service.save()

        # Load in new service
        new_config = AppConfig()
        new_service = ModelManagerService[AppConfig](AppConfig, new_config, service._default_path)
        new_service.load()

        assert new_service.get("auto_save") is False
        assert new_service.get("default_buffer_size") == 2048
