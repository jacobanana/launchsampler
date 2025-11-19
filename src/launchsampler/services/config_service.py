"""Configuration service for managing application configuration."""

import logging
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar, Type
from threading import Lock

from pydantic import BaseModel, ValidationError

from launchsampler.protocols import ConfigEvent, ConfigObserver
from launchsampler.utils import ObserverManager, PydanticPersistence

logger = logging.getLogger(__name__)

# Generic type for any Pydantic config model
ConfigType = TypeVar('ConfigType', bound=BaseModel)


class ConfigService(Generic[ConfigType]):
    """
    Generic service for managing Pydantic-based configuration.

    This service provides a centralized way to manage any Pydantic configuration
    model with get/set operations, persistence, and event notifications.

    Design Philosophy:
        - Generic: Works with ANY Pydantic BaseModel subclass
        - Type-safe: Full type hinting and validation via Pydantic
        - Observable: Emits events for all config changes
        - Thread-safe: Protected by locks for concurrent access
        - Single responsibility: Only handles config management

    Event-Driven Architecture:
        All configuration operations emit ConfigEvent notifications to registered
        observers. This ensures automatic synchronization of dependent components
        without manual coordination.

    Threading:
        All public methods are thread-safe. The _lock protects config state
        during reads/writes. The lock is released before notifying observers
        to prevent deadlocks (same pattern as other services).

    Usage Example:
        ```python
        # Create service with AppConfig
        config = AppConfig.load_or_default()
        service = ConfigService[AppConfig](AppConfig, config)

        # Register observers
        service.register_observer(my_observer)

        # Get values
        auto_save = service.get("auto_save")

        # Set values
        service.set("auto_save", False)

        # Save to disk
        service.save()
        ```
    """

    def __init__(
        self,
        config_type: Type[ConfigType],
        initial_config: ConfigType,
        default_path: Optional[Path] = None
    ):
        """
        Initialize the configuration service.

        Args:
            config_type: The Pydantic model class (e.g., AppConfig)
            initial_config: The initial configuration instance
            default_path: Default path for save/load operations (optional)
        """
        self._config_type = config_type
        self._config = initial_config
        self._default_path = default_path
        self._lock = Lock()

        # Event system
        self._observers = ObserverManager[ConfigObserver](
            lock=self._lock,
            observer_type_name="config"
        )

        logger.info(f"ConfigService initialized with {config_type.__name__}")

    # =================================================================
    # Event System
    # =================================================================

    def register_observer(self, observer: ConfigObserver) -> None:
        """
        Register an observer to receive configuration events.

        Args:
            observer: Object implementing ConfigObserver protocol
        """
        self._observers.register(observer)

    def unregister_observer(self, observer: ConfigObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        self._observers.unregister(observer)

    def _notify_observers(self, event: ConfigEvent, **kwargs: Any) -> None:
        """
        Notify all registered observers of a configuration event.

        Args:
            event: The configuration event that occurred
            **kwargs: Event-specific data

        Note:
            ObserverManager handles exception catching and logging automatically.
        """
        self._observers.notify('on_config_event', event, **kwargs)

    # =================================================================
    # Configuration Access
    # =================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration field name
            default: Default value if key doesn't exist

        Returns:
            The configuration value, or default if key doesn't exist

        Thread-Safety:
            This method is thread-safe. Config state is protected by lock.

        Example:
            ```python
            auto_save = service.get("auto_save")
            buffer_size = service.get("default_buffer_size", 512)
            ```
        """
        with self._lock:
            return getattr(self._config, key, default)

    def get_all(self) -> dict[str, Any]:
        """
        Get all configuration values as a dictionary.

        Returns:
            Dictionary of all config field names and values

        Thread-Safety:
            This method is thread-safe. Returns a snapshot of config state.

        Example:
            ```python
            all_config = service.get_all()
            print(f"Sets directory: {all_config['sets_dir']}")
            ```
        """
        with self._lock:
            return self._config.model_dump()

    def get_config(self) -> ConfigType:
        """
        Get a copy of the entire configuration object.

        Returns:
            Deep copy of the current configuration

        Thread-Safety:
            This method is thread-safe. Returns a deep copy to prevent
            external mutation.

        Example:
            ```python
            config_copy = service.get_config()
            # Safe to modify config_copy without affecting service state
            ```
        """
        with self._lock:
            return self._config.model_copy(deep=True)

    # =================================================================
    # Configuration Mutation
    # =================================================================

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value by key.

        Args:
            key: Configuration field name
            value: New value (must be valid for the field type)

        Raises:
            AttributeError: If key doesn't exist in config model
            ValidationError: If value fails Pydantic validation

        Thread-Safety:
            This method is thread-safe. Config state is protected by lock.

        Events:
            Emits CONFIG_UPDATED with keys=[key], values={key: value}

        Example:
            ```python
            service.set("auto_save", False)
            service.set("default_buffer_size", 1024)
            ```
        """
        with self._lock:
            if not hasattr(self._config, key):
                raise AttributeError(
                    f"'{self._config_type.__name__}' has no field '{key}'"
                )

            # Validate by reconstructing the model (Pydantic 2.x doesn't validate on setattr/model_copy)
            try:
                current_dict = self._config.model_dump()
                current_dict[key] = value
                self._config = self._config_type.model_validate(current_dict)
                updated_values = {key: value}
            except ValidationError as e:
                logger.error(f"Validation error setting {key}={value}: {e}")
                raise

        # Notify observers (outside lock)
        self._notify_observers(
            ConfigEvent.CONFIG_UPDATED,
            keys=[key],
            values=updated_values
        )

        logger.debug(f"Config updated: {key}={value}")

    def update(self, values: dict[str, Any]) -> None:
        """
        Update multiple configuration values at once.

        Args:
            values: Dictionary of field names and values to update

        Raises:
            AttributeError: If any key doesn't exist in config model
            ValidationError: If any value fails Pydantic validation

        Thread-Safety:
            This method is thread-safe. All updates are atomic.

        Events:
            Emits single CONFIG_UPDATED event with all changed keys/values

        Example:
            ```python
            service.update({
                "auto_save": False,
                "default_buffer_size": 1024,
                "midi_poll_interval": 1.0
            })
            ```
        """
        with self._lock:
            # Validate all keys exist first
            for key in values:
                if not hasattr(self._config, key):
                    raise AttributeError(
                        f"'{self._config_type.__name__}' has no field '{key}'"
                    )

            # Apply all updates with validation (atomic - all or nothing)
            try:
                current_dict = self._config.model_dump()
                current_dict.update(values)
                self._config = self._config_type.model_validate(current_dict)
            except ValidationError as e:
                logger.error(f"Validation error during batch update: {e}")
                raise

        # Notify observers (outside lock)
        self._notify_observers(
            ConfigEvent.CONFIG_UPDATED,
            keys=list(values.keys()),
            values=values
        )

        logger.debug(f"Config batch updated: {list(values.keys())}")

    def reset(self) -> None:
        """
        Reset configuration to default values.

        Thread-Safety:
            This method is thread-safe. Config replacement is atomic.

        Events:
            Emits CONFIG_RESET with the new default config

        Example:
            ```python
            service.reset()
            # All config values are now back to defaults
            ```
        """
        with self._lock:
            # Create new default instance
            self._config = self._config_type()

        # Notify observers (outside lock)
        self._notify_observers(
            ConfigEvent.CONFIG_RESET,
            config=self._config.model_copy(deep=True)
        )

        logger.info(f"Config reset to defaults: {self._config_type.__name__}")

    # =================================================================
    # Persistence
    # =================================================================

    def load(self, path: Optional[Path] = None) -> None:
        """
        Load configuration from file.

        Args:
            path: Path to config file (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set
            ValidationError: If config file has invalid values
            FileNotFoundError: If config file doesn't exist

        Thread-Safety:
            This method is thread-safe. Config replacement is atomic.

        Events:
            Emits CONFIG_LOADED with the file path

        Example:
            ```python
            service.load(Path("~/.launchsampler/config.json"))
            # or use default path:
            service.load()
            ```
        """
        file_path = path or self._default_path
        if file_path is None:
            raise ValueError("No path specified and no default_path set")

        # Load and validate from file using shared utility
        new_config = PydanticPersistence.load_json(file_path, self._config_type)

        with self._lock:
            self._config = new_config

        # Notify observers (outside lock)
        self._notify_observers(
            ConfigEvent.CONFIG_LOADED,
            path=file_path
        )

        logger.info(f"Config loaded from {file_path}")

    def save(self, path: Optional[Path] = None) -> None:
        """
        Save configuration to file.

        Args:
            path: Path to save config to (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set

        Thread-Safety:
            This method is thread-safe. Config is read under lock.

        Events:
            Emits CONFIG_SAVED with the file path

        Example:
            ```python
            service.save(Path("~/.launchsampler/config.json"))
            # or use default path:
            service.save()
            ```
        """
        file_path = path or self._default_path
        if file_path is None:
            raise ValueError("No path specified and no default_path set")

        file_path = Path(file_path)

        # Get config copy while holding lock
        with self._lock:
            config_copy = self._config.model_copy(deep=True)

        # Write to file using shared utility (outside lock - I/O can be slow)
        PydanticPersistence.save_json(config_copy, file_path)

        # Notify observers (outside lock)
        self._notify_observers(
            ConfigEvent.CONFIG_SAVED,
            path=file_path
        )

        logger.info(f"Config saved to {file_path}")

    def reload(self, path: Optional[Path] = None) -> None:
        """
        Reload configuration from file (convenience method).

        This is equivalent to calling load() but provides clearer intent.

        Args:
            path: Path to config file (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set
            ValidationError: If config file has invalid values
            FileNotFoundError: If config file doesn't exist

        Example:
            ```python
            # Reload from disk (discard in-memory changes)
            service.reload()
            ```
        """
        self.load(path)
