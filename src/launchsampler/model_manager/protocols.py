"""Protocol definitions for model management framework.

This module defines the core protocols and events for the model management system:
- ModelEvent: Events from model lifecycle (load, save, update, reset)
- ModelObserver: Observer protocol for model change notifications
- PersistenceService: Protocol for persistence service implementations
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

# Type variable for persistence services
T = TypeVar("T", bound="BaseModel")


class ModelEvent(Enum):
    """Events from model changes (configuration, sets, etc.)."""

    MODEL_LOADED = "model_loaded"  # Model was loaded from disk
    MODEL_SAVED = "model_saved"  # Model was saved to disk
    MODEL_UPDATED = "model_updated"  # Model value(s) were updated
    MODEL_RESET = "model_reset"  # Model was reset to defaults


@runtime_checkable
class ModelObserver(Protocol):
    """
    Observer that receives model change events.

    This protocol allows loose coupling between model manager services
    and components that need to react to model changes.
    """

    def on_model_event(self, event: "ModelEvent", **kwargs) -> None:
        """
        Handle model change events.

        Args:
            event: The type of model event
            **kwargs: Event-specific data:
                - For MODEL_UPDATED: 'keys' (list of changed keys), 'values' (dict of new values)
                - For MODEL_LOADED/MODEL_SAVED: 'path' (Path to model file)
                - For MODEL_RESET: 'model' (the new default model)

        Threading:
            Called from the thread that initiated the model change.
            Implementations should be thread-safe and avoid blocking operations.

        Error Handling:
            Exceptions raised by observers are caught and logged by the
            ModelManagerService. They do not propagate to the caller, ensuring
            one failing observer doesn't break others.
        """
        ...


@runtime_checkable
class PersistenceService[T: "BaseModel"](Protocol):
    """
    Protocol for services that persist Pydantic models to/from JSON files.

    This protocol defines a common interface for services that handle
    loading and saving Pydantic models, ensuring consistency across
    ConfigService, SetManagerService, and other persistence services.

    Type Parameter:
        T: The Pydantic BaseModel type this service persists

    Design Philosophy:
        - Explicit interface for persistence operations
        - Allows both stateful (ConfigService) and stateless (SetManagerService) implementations
        - Does not prescribe internal state management or caching
        - Enables composition over inheritance

    Example Implementations:
        - ConfigService: Stateful service with mutable config and observers
        - SetManagerService: Stateless service that operates on Set objects
        - DeviceRegistry: Read-only service that loads once at init
    """

    def load(self, path: Path) -> T:
        """
        Load a Pydantic model from a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            Loaded and validated model instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValidationError: If the file content is invalid
            ValueError: If the file format is incorrect

        Thread-Safety:
            Implementations should document their thread-safety guarantees.
        """
        ...

    def save(self, data: T, path: Path) -> None:
        """
        Save a Pydantic model to a JSON file.

        Args:
            data: The model instance to save
            path: Path where the file should be saved

        Raises:
            ValueError: If save operation fails
            OSError: If file cannot be written

        Notes:
            - Implementations should create parent directories if needed
            - Implementations may perform transformations before saving
              (e.g., SetManagerService resolves relative paths)

        Thread-Safety:
            Implementations should document their thread-safety guarantees.
        """
        ...
