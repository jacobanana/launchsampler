"""Shared utilities for Pydantic model persistence.

This module provides reusable functions for loading and saving Pydantic models
to/from JSON files. These utilities follow DRY principles and eliminate code
duplication across ConfigService, SetManagerService, and other persistence services.

Design Philosophy:
    - Stateless utility functions (no internal state)
    - Composition over inheritance
    - Centralized error handling with custom exceptions
    - Thread-safe (no shared mutable state)
    - Works with any Pydantic BaseModel subclass

Error Handling:
    Uses the centralized error handler (utils/error_handler.py) to convert
    low-level Pydantic/IO errors into user-friendly LaunchSamplerError exceptions
    with recovery hints and consistent messaging.

Safety Features:
    - Automatic .bak backups before overwriting files
    - Atomic writes using temp file + rename
    - Never auto-saves over corrupted files
    - Only auto-saves when file is missing (FileNotFoundError)
"""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from launchsampler.exceptions import ConfigurationError, wrap_pydantic_error

logger = logging.getLogger(__name__)

# Type variable bound to Pydantic BaseModel
T = TypeVar("T", bound=BaseModel)


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
    def load_json(path: Path, model_type: type[T]) -> T:
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
            ConfigFileInvalidError: If the JSON syntax is invalid
            ConfigValidationError: If the JSON content fails Pydantic validation
            ConfigurationError: For other configuration-related errors

        Example:
            ```python
            config = PydanticPersistence.load_json(
                Path("~/.config/app.json"),
                AppConfig
            )
            ```

        Note:
            Uses centralized error handler to convert Pydantic ValidationError
            to user-friendly exceptions with recovery hints.
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            # Read file content
            json_content = path.read_text()

            if not json_content or not json_content.strip():
                from launchsampler.exceptions import ConfigFileInvalidError

                raise ConfigFileInvalidError(str(path), "File is empty")

            # Validate and parse with Pydantic
            model = model_type.model_validate_json(json_content)

            logger.debug(f"Loaded {model_type.__name__} from {path}")
            return model

        except ValidationError as e:
            # Convert to user-friendly exception using centralized error handler
            logger.error(f"Validation error loading {model_type.__name__} from {path}: {e}")
            raise wrap_pydantic_error(e, str(path)) from e

        except ConfigurationError:
            # Re-raise our custom configuration errors
            raise

        except Exception as e:
            # Unexpected errors - wrap in ConfigurationError
            logger.error(f"Unexpected error loading {model_type.__name__} from {path}: {e}")
            from launchsampler.exceptions import ConfigFileInvalidError

            raise ConfigFileInvalidError(str(path), f"Unexpected error: {e}") from e

    @staticmethod
    def save_json(
        data: BaseModel,
        path: Path,
        indent: int = 2,
        create_parents: bool = True,
        backup: bool = True,
    ) -> None:
        """
        Save a Pydantic model to a JSON file with automatic backup and atomic write.

        This method implements safety features to prevent data loss:
        1. Creates .bak backup of existing file before overwriting
        2. Uses atomic write (temp file + rename) to prevent corruption
        3. Serializes the Pydantic model to JSON
        4. Creates parent directories (if requested)

        Args:
            data: The Pydantic model instance to save
            path: Path where the file should be saved
            indent: JSON indentation level (default: 2 spaces)
            create_parents: Create parent directories if they don't exist (default: True)
            backup: Create .bak backup before overwriting existing file (default: True)

        Raises:
            OSError: If the file cannot be written (permission denied, disk full, etc.)
            ConfigurationError: If serialization or save fails

        Example:
            ```python
            PydanticPersistence.save_json(
                data=config,
                path=Path("~/.config/app.json"),
                indent=2,
                backup=True  # Creates app.json.bak before overwriting
            )
            ```

        Safety Notes:
            - Backup file (.bak) is created before overwriting (if file exists)
            - Atomic write prevents corruption if write is interrupted
            - Parent directories are created by default
            - JSON is pretty-printed with configurable indentation
        """
        try:
            # Create parent directories if requested
            if create_parents and path.parent:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists and backup is requested
            if backup and path.exists():
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)
                logger.debug(f"Created backup: {backup_path}")

            # Serialize to JSON
            json_content = data.model_dump_json(indent=indent)

            # Atomic write: write to temp file first, then rename
            temp_path = path.with_suffix(path.suffix + ".tmp")
            try:
                temp_path.write_text(json_content, encoding="utf-8")
                # Atomic rename (overwrites destination on most systems)
                temp_path.replace(path)
                logger.debug(f"Saved {type(data).__name__} to {path}")
            finally:
                # Clean up temp file if it still exists (failed rename)
                if temp_path.exists():
                    temp_path.unlink()

        except OSError as e:
            # File system errors (permission, disk full, etc.) - re-raise as-is
            logger.error(f"OS error saving {type(data).__name__} to {path}: {e}")
            raise

        except Exception as e:
            # Unexpected errors - wrap in ConfigurationError
            logger.error(f"Unexpected error saving {type(data).__name__} to {path}: {e}")
            raise ConfigurationError(
                user_message=f"Failed to save configuration to {path}",
                technical_message=f"Failed to save {type(data).__name__}: {e}",
                recovery_hint="Check file permissions and disk space. Backup file (.bak) may be available.",
            ) from e

    @staticmethod
    def load_json_or_default(
        path: Path, model_type: type[T], default_factory: Callable | None = None
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
            ConfigFileInvalidError: If the file exists but has invalid JSON syntax
            ConfigValidationError: If the file exists but has invalid values
            ConfigurationError: For other configuration-related errors

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
            - Other errors (ConfigurationError subclasses) are propagated
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
    def validate_json(path: Path, model_type: type[T]) -> tuple[bool, str | None]:
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
        except ConfigurationError as e:
            # Use user-friendly message from custom exception
            return False, e.user_message
        except Exception as e:
            return False, f"Error: {e}"

    @staticmethod
    def ensure_valid_or_create(
        path: Path,
        model_type: type[T],
        default_factory: Callable | None = None,
        auto_save: bool = True,
    ) -> T:
        """
        Ensure a valid JSON file exists, creating a default if needed.

        This method implements safe default handling:
        1. Tries to load the file
        2. If file doesn't exist: creates default and saves (if auto_save=True)
        3. If file is corrupted: creates default but DOES NOT save over corrupted file

        Args:
            path: Path to the JSON file
            model_type: The Pydantic model class
            default_factory: Optional callable that returns a default instance
            auto_save: Automatically save default to disk if file is missing (default: True)

        Returns:
            Valid model instance (loaded or newly created)

        Example:
            ```python
            config = PydanticPersistence.ensure_valid_or_create(
                path=Path("config.json"),
                model_type=AppConfig,
                auto_save=True
            )
            # config.json exists with valid data (or defaults are used without overwriting)
            ```

        Safety Notes:
            - ONLY auto-saves when file is missing (FileNotFoundError)
            - NEVER overwrites corrupted files (ConfigurationError)
            - Corrupted files are preserved for manual recovery
            - Creates .bak backup before any overwrite (when auto_save=True)
        """
        try:
            return PydanticPersistence.load_json(path, model_type)
        except FileNotFoundError:
            # File doesn't exist - safe to create and save default
            logger.info(f"File not found: {path}, creating default {model_type.__name__}")

            # Create default instance
            instance = default_factory() if default_factory else model_type()

            # Auto-save if requested (no backup needed since file doesn't exist)
            if auto_save:
                PydanticPersistence.save_json(instance, path, backup=False)
                logger.info(f"Saved default {model_type.__name__} to {path}")

            return instance

        except ConfigurationError as e:
            # File exists but is corrupted - DO NOT auto-save over it!
            logger.error(f"Failed to load {path}: {e.user_message}")
            logger.warning(
                f"Using default {model_type.__name__} configuration "
                f"(existing file NOT overwritten - manual recovery may be possible)"
            )

            # Return default but preserve corrupted file
            if default_factory:
                return default_factory()
            else:
                return model_type()
