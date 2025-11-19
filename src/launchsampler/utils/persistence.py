"""Shared utilities for Pydantic model persistence.

This module provides reusable functions for loading and saving Pydantic models
to/from JSON files. These utilities follow DRY principles and eliminate code
duplication across ConfigService, SetManagerService, and other persistence services.

Design Philosophy:
    - Stateless utility functions (no internal state)
    - Composition over inheritance
    - Explicit error handling with custom exceptions
    - Thread-safe (no shared mutable state)
    - Works with any Pydantic BaseModel subclass
"""

import logging
from pathlib import Path
from typing import Callable, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# Type variable bound to Pydantic BaseModel
T = TypeVar('T', bound=BaseModel)


class PydanticPersistence:
    """
    Utility class providing shared Pydantic persistence operations.

    This class provides stateless utility methods for loading and saving
    Pydantic models to/from JSON files. All methods are static and can be
    used without instantiation.

    Example Usage:
        ```python
        # Load a config
        config = PydanticPersistence.load_json(
            path=Path("config.json"),
            model_type=AppConfig
        )

        # Save a config
        PydanticPersistence.save_json(
            data=config,
            path=Path("config.json")
        )
        ```

    Thread-Safety:
        All methods are thread-safe as they operate on function parameters
        and do not access shared mutable state.
    """

    @staticmethod
    def load_json(path: Path, model_type: Type[T]) -> T:
        """
        Load and validate a Pydantic model from a JSON file.

        This method:
        1. Reads the JSON file
        2. Validates it against the Pydantic model schema
        3. Returns a fully validated model instance

        Args:
            path: Path to the JSON file to load
            model_type: The Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValidationError: If the JSON content fails Pydantic validation
            ValueError: If the JSON is malformed or empty

        Example:
            ```python
            config = PydanticPersistence.load_json(
                Path("~/.config/app.json"),
                AppConfig
            )
            ```
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            # Read file content
            json_content = path.read_text()

            if not json_content or not json_content.strip():
                raise ValueError(f"File is empty: {path}")

            # Validate and parse with Pydantic
            model = model_type.model_validate_json(json_content)

            logger.debug(f"Loaded {model_type.__name__} from {path}")
            return model

        except ValidationError as e:
            logger.error(f"Validation error loading {model_type.__name__} from {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading {model_type.__name__} from {path}: {e}")
            raise ValueError(f"Failed to load {model_type.__name__}: {e}") from e

    @staticmethod
    def save_json(
        data: BaseModel,
        path: Path,
        indent: int = 2,
        create_parents: bool = True
    ) -> None:
        """
        Save a Pydantic model to a JSON file.

        This method:
        1. Serializes the Pydantic model to JSON
        2. Creates parent directories (if requested)
        3. Writes the JSON to the file

        Args:
            data: The Pydantic model instance to save
            path: Path where the file should be saved
            indent: JSON indentation level (default: 2 spaces)
            create_parents: Create parent directories if they don't exist (default: True)

        Raises:
            OSError: If the file cannot be written
            ValueError: If serialization fails

        Example:
            ```python
            PydanticPersistence.save_json(
                data=config,
                path=Path("~/.config/app.json"),
                indent=2
            )
            ```

        Notes:
            - The file will be overwritten if it exists
            - Parent directories are created by default
            - JSON is pretty-printed with configurable indentation
        """
        try:
            # Create parent directories if requested
            if create_parents and path.parent:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize to JSON
            json_content = data.model_dump_json(indent=indent)

            # Write to file
            path.write_text(json_content)

            logger.debug(f"Saved {type(data).__name__} to {path}")

        except Exception as e:
            logger.error(f"Error saving {type(data).__name__} to {path}: {e}")
            raise ValueError(f"Failed to save {type(data).__name__}: {e}") from e

    @staticmethod
    def load_json_or_default(
        path: Path,
        model_type: Type[T],
        default_factory: Optional[Callable] = None
    ) -> T:
        """
        Load a model from JSON, or return a default if the file doesn't exist.

        This is a convenience method that combines load_json with fallback logic.
        Useful for configuration files that should be auto-created with defaults.

        Args:
            path: Path to the JSON file
            model_type: The Pydantic model class
            default_factory: Optional callable that returns a default instance.
                           If None, calls model_type() to get defaults.

        Returns:
            Loaded model instance, or default instance if file doesn't exist

        Raises:
            ValidationError: If the file exists but has invalid content

        Example:
            ```python
            config = PydanticPersistence.load_json_or_default(
                path=Path("config.json"),
                model_type=AppConfig,
                default_factory=lambda: AppConfig(debug=True)
            )
            ```

        Notes:
            - FileNotFoundError is caught and triggers default creation
            - Other errors (ValidationError, etc.) are propagated
            - Does not automatically save the default to disk
        """
        try:
            return PydanticPersistence.load_json(path, model_type)
        except FileNotFoundError:
            logger.info(f"File not found: {path}, creating default {model_type.__name__}")
            if default_factory:
                return default_factory()
            else:
                return model_type()

    @staticmethod
    def validate_json(path: Path, model_type: Type[T]) -> tuple[bool, Optional[str]]:
        """
        Validate a JSON file against a Pydantic model without loading it.

        This is useful for pre-flight checks or validation tools.

        Args:
            path: Path to the JSON file
            model_type: The Pydantic model class to validate against

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file is valid, False otherwise
            - error_message: None if valid, error description if invalid

        Example:
            ```python
            is_valid, error = PydanticPersistence.validate_json(
                Path("config.json"),
                AppConfig
            )
            if not is_valid:
                print(f"Invalid config: {error}")
            ```
        """
        try:
            PydanticPersistence.load_json(path, model_type)
            return True, None
        except FileNotFoundError:
            return False, f"File not found: {path}"
        except ValidationError as e:
            return False, f"Validation error: {e}"
        except Exception as e:
            return False, f"Error: {e}"

    @staticmethod
    def ensure_valid_or_create(
        path: Path,
        model_type: Type[T],
        default_factory: Optional[Callable] = None,
        auto_save: bool = True
    ) -> T:
        """
        Ensure a valid JSON file exists, creating a default if needed.

        This method:
        1. Tries to load the file
        2. If file doesn't exist or is invalid, creates a default
        3. Optionally saves the default to disk

        Args:
            path: Path to the JSON file
            model_type: The Pydantic model class
            default_factory: Optional callable that returns a default instance
            auto_save: Automatically save default to disk if created (default: True)

        Returns:
            Valid model instance (loaded or newly created)

        Example:
            ```python
            config = PydanticPersistence.ensure_valid_or_create(
                path=Path("config.json"),
                model_type=AppConfig,
                auto_save=True
            )
            # config.json is guaranteed to exist with valid data
            ```

        Notes:
            - Validation errors trigger default creation (file is corrupted)
            - The default is saved to disk if auto_save=True
        """
        try:
            return PydanticPersistence.load_json(path, model_type)
        except (FileNotFoundError, ValidationError) as e:
            logger.warning(f"Creating default {model_type.__name__}: {e}")

            # Create default instance
            if default_factory:
                instance = default_factory()
            else:
                instance = model_type()

            # Auto-save if requested
            if auto_save:
                PydanticPersistence.save_json(instance, path)
                logger.info(f"Saved default {model_type.__name__} to {path}")

            return instance
