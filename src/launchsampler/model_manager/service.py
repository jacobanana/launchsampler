"""Model manager service for managing Pydantic models (config, sets, etc.)."""

import logging
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from launchsampler.model_manager.observer import ObserverManager
from launchsampler.model_manager.persistence import PydanticPersistence
from launchsampler.model_manager.protocols import ModelEvent, ModelObserver

logger = logging.getLogger(__name__)

# Generic type for any Pydantic model
ModelType = TypeVar("ModelType", bound=BaseModel)


class ModelManagerService[ModelType: BaseModel]:
    """
    Generic service for managing Pydantic-based models.

    This service provides a centralized way to manage any Pydantic model
    (AppConfig, Set, or other models) with get/set operations, persistence,
    and event notifications.

    Design Philosophy:
        - Generic: Works with ANY Pydantic BaseModel subclass
        - Type-safe: Full type hinting and validation via Pydantic
        - Observable: Emits events for all model changes
        - Thread-safe: Protected by locks for concurrent access
        - Single responsibility: Only handles model state management

    Event-Driven Architecture:
        All model operations emit ModelEvent notifications to registered
        observers. This ensures automatic synchronization of dependent components
        without manual coordination.

    Threading:
        All public methods are thread-safe. The _lock protects model state
        during reads/writes. The lock is released before notifying observers
        to prevent deadlocks (same pattern as other services).

    Usage Example:
        ```python
        # Create service with AppConfig
        config = AppConfig.load_or_default()
        service = ModelManagerService[AppConfig](AppConfig, config)

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
        model_type: type[ModelType],
        initial_model: ModelType,
        default_path: Path | None = None,
    ):
        """
        Initialize the model manager service.

        Args:
            model_type: The Pydantic model class (e.g., AppConfig, Set)
            initial_model: The initial model instance
            default_path: Default path for save/load operations (optional)
        """
        self._model_type = model_type
        self._model = initial_model
        self._default_path = default_path
        self._lock = Lock()

        # Event system
        self._observers = ObserverManager[ModelObserver](
            lock=self._lock, observer_type_name="model"
        )

        logger.info(f"ModelManagerService initialized with {model_type.__name__}")

    # =================================================================
    # Event System
    # =================================================================

    def register_observer(self, observer: ModelObserver) -> None:
        """
        Register an observer to receive model change events.

        Args:
            observer: Object implementing ModelObserver protocol
        """
        self._observers.register(observer)

    def unregister_observer(self, observer: ModelObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        self._observers.unregister(observer)

    def _notify_observers(self, event: ModelEvent, **kwargs: Any) -> None:
        """
        Notify all registered observers of a model change event.

        Args:
            event: The model event that occurred
            **kwargs: Event-specific data

        Note:
            ObserverManager handles exception catching and logging automatically.
        """
        self._observers.notify("on_model_event", event, **kwargs)

    # =================================================================
    # Model Access
    # =================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a model field value by key.

        Args:
            key: Model field name
            default: Default value if key doesn't exist

        Returns:
            The field value, or default if key doesn't exist

        Thread-Safety:
            This method is thread-safe. Model state is protected by lock.

        Example:
            ```python
            auto_save = service.get("auto_save")
            buffer_size = service.get("default_buffer_size", 512)
            ```
        """
        with self._lock:
            return getattr(self._model, key, default)

    def get_all(self) -> dict[str, Any]:
        """
        Get all model field values as a dictionary.

        Returns:
            Dictionary of all model field names and values

        Thread-Safety:
            This method is thread-safe. Returns a snapshot of model state.

        Example:
            ```python
            all_fields = service.get_all()
            print(f"Sets directory: {all_fields['sets_dir']}")
            ```
        """
        with self._lock:
            return self._model.model_dump()

    def get_model(self) -> ModelType:
        """
        Get a copy of the entire model object.

        Returns:
            Deep copy of the current model

        Thread-Safety:
            This method is thread-safe. Returns a deep copy to prevent
            external mutation.

        Example:
            ```python
            model_copy = service.get_model()
            # Safe to modify model_copy without affecting service state
            ```
        """
        with self._lock:
            return self._model.model_copy(deep=True)

    # =================================================================
    # Model Mutation
    # =================================================================

    def set(self, key: str, value: Any) -> None:
        """
        Set a model field value by key.

        Args:
            key: Model field name
            value: New value (must be valid for the field type)

        Raises:
            AttributeError: If key doesn't exist in model
            ValidationError: If value fails Pydantic validation

        Thread-Safety:
            This method is thread-safe. Model state is protected by lock.

        Events:
            Emits MODEL_UPDATED with keys=[key], values={key: value}

        Example:
            ```python
            service.set("auto_save", False)
            service.set("default_buffer_size", 1024)
            ```
        """
        with self._lock:
            if not hasattr(self._model, key):
                raise AttributeError(f"'{self._model_type.__name__}' has no field '{key}'")

            # Validate by reconstructing the model (Pydantic 2.x doesn't validate on setattr/model_copy)
            try:
                current_dict = self._model.model_dump()
                current_dict[key] = value
                self._model = self._model_type.model_validate(current_dict)
                updated_values = {key: value}
            except ValidationError as e:
                logger.error(f"Validation error setting {key}={value}: {e}")
                raise

        # Notify observers (outside lock)
        self._notify_observers(ModelEvent.MODEL_UPDATED, keys=[key], values=updated_values)

        logger.debug(f"Model updated: {key}={value}")

    def update(self, values: dict[str, Any]) -> None:
        """
        Update multiple model field values at once.

        Args:
            values: Dictionary of field names and values to update

        Raises:
            AttributeError: If any key doesn't exist in model
            ValidationError: If any value fails Pydantic validation

        Thread-Safety:
            This method is thread-safe. All updates are atomic.

        Events:
            Emits single MODEL_UPDATED event with all changed keys/values

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
                if not hasattr(self._model, key):
                    raise AttributeError(f"'{self._model_type.__name__}' has no field '{key}'")

            # Apply all updates with validation (atomic - all or nothing)
            try:
                current_dict = self._model.model_dump()
                current_dict.update(values)
                self._model = self._model_type.model_validate(current_dict)
            except ValidationError as e:
                logger.error(f"Validation error during batch update: {e}")
                raise

        # Notify observers (outside lock)
        self._notify_observers(ModelEvent.MODEL_UPDATED, keys=list(values.keys()), values=values)

        logger.debug(f"Model batch updated: {list(values.keys())}")

    def reset(self) -> None:
        """
        Reset model to default values.

        Thread-Safety:
            This method is thread-safe. Model replacement is atomic.

        Events:
            Emits MODEL_RESET with the new default model

        Example:
            ```python
            service.reset()
            # All model field values are now back to defaults
            ```
        """
        with self._lock:
            # Create new default instance
            self._model = self._model_type()

        # Notify observers (outside lock)
        self._notify_observers(ModelEvent.MODEL_RESET, model=self._model.model_copy(deep=True))

        logger.info(f"Model reset to defaults: {self._model_type.__name__}")

    # =================================================================
    # Persistence
    # =================================================================

    def load(self, path: Path | None = None) -> None:
        """
        Load model from file.

        Args:
            path: Path to model file (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set
            ValidationError: If model file has invalid values
            FileNotFoundError: If model file doesn't exist

        Thread-Safety:
            This method is thread-safe. Model replacement is atomic.

        Events:
            Emits MODEL_LOADED with the file path

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
        new_model = PydanticPersistence.load_json(file_path, self._model_type)

        with self._lock:
            self._model = new_model

        # Notify observers (outside lock)
        self._notify_observers(ModelEvent.MODEL_LOADED, path=file_path)

        logger.info(f"Model loaded from {file_path}")

    def save(self, path: Path | None = None) -> None:
        """
        Save model to file.

        Args:
            path: Path to save model to (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set

        Thread-Safety:
            This method is thread-safe. Model is read under lock.

        Events:
            Emits MODEL_SAVED with the file path

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

        # Get model copy while holding lock
        with self._lock:
            model_copy = self._model.model_copy(deep=True)

        # Write to file using shared utility (outside lock - I/O can be slow)
        PydanticPersistence.save_json(model_copy, file_path)

        # Notify observers (outside lock)
        self._notify_observers(ModelEvent.MODEL_SAVED, path=file_path)

        logger.info(f"Model saved to {file_path}")

    def reload(self, path: Path | None = None) -> None:
        """
        Reload model from file (convenience method).

        This is equivalent to calling load() but provides clearer intent.

        Args:
            path: Path to model file (uses default_path if None)

        Raises:
            ValueError: If no path specified and no default_path set
            ValidationError: If model file has invalid values
            FileNotFoundError: If model file doesn't exist

        Example:
            ```python
            # Reload from disk (discard in-memory changes)
            service.reload()
            ```
        """
        self.load(path)
