"""
Centralized error handling utilities.

This module provides a systematic, layered approach to error handling:

1. **Custom Exceptions** - Typed, user-friendly error classes (see base, audio, config modules)
2. **Error Context** - Preserve technical details for logging, show friendly messages to users
3. **Recovery Hints** - Tell users what to do when things fail
4. **Error Isolation** - One failure shouldn't cascade to others

## Quick Reference

### When to Use What

| Scenario | Use This | Example |
|----------|----------|---------|
| Audio device in use | `AudioDeviceInUseError` | `raise AudioDeviceInUseError(device_id=3)` |
| Audio device not found | `AudioDeviceNotFoundError` | `raise AudioDeviceNotFoundError(device_id=5)` |
| Config file syntax error | `ConfigFileInvalidError` | `raise ConfigFileInvalidError(path, "trailing comma")` |
| Config value invalid | `ConfigValidationError` | `raise ConfigValidationError("buffer_size", 99, "must be power of 2")` |

### Handling Patterns

| Pattern | Code |
|---------|------|
| Show error to user, continue | `@handle_errors(operation_name="load", user_notification=self.notify, re_raise=False)` |
| Log and re-raise | `@handle_errors(operation_name="init", re_raise=True)` |
| Try multiple ops, collect errors | `collector = collect_errors("load samples"); with collector.try_operation(...): ...` |
| Critical section with auto-logging | `with ErrorContext("initialize player"): ...` |

## Examples

### Example 1: Converting Low-Level Errors

```python
from launchsampler.exceptions import wrap_audio_device_error

try:
    self._stream = sd.OutputStream(**config)
    self._stream.start()
except Exception as e:
    # Automatically converts to appropriate exception type
    raise wrap_audio_device_error(e, device_id=self.device)
```

Benefits:
- Error detection logic centralized
- Consistent user messages
- Recovery hints included automatically

### Example 2: Config Validation with Custom Exceptions

```python
from launchsampler.exceptions import wrap_pydantic_error

try:
    config = AppConfig.model_validate_json(path.read_text())
except ValidationError as e:
    # Converts Pydantic error to user-friendly ConfigValidationError
    raise wrap_pydantic_error(e, str(path)) from e
```

Benefits:
- Automatic field name extraction
- User-friendly error messages
- Field-specific recovery hints (audio devices, MIDI, etc.)

### Example 3: Batch Operations (Loading Multiple Samples)

```python
from launchsampler.exceptions import collect_errors

def load_samples_from_directory(self, directory: Path):
    '''Load all samples from a directory.'''
    collector = collect_errors("load samples")

    for file in directory.glob("*.wav"):
        with collector.try_operation(f"load {file.name}"):
            self.load_sample(file)

    if collector.has_errors:
        self.notify(collector.get_summary(), severity="error")
    else:
        self.notify(f"Loaded {collector.success_count} samples")
```

Benefits:
- Shows ALL failures, not just first one
- Continues trying even after failures
- Nice summary message

### Example 4: Critical Initialization

```python
from launchsampler.exceptions import ErrorContext

def initialize(self):
    with ErrorContext("initialize player", logger_instance=logger):
        self.player = Player(self.config)
        self.player.start()
```

Benefits:
- Automatic logging of start and completion
- Exception details preserved

## Best Practices

### DO

✅ Use specific exception types:
```python
raise AudioDeviceInUseError(device_id=3)  # Good
```

✅ Provide recovery hints:
```python
raise ValidationError("volume", 150, "must be 0-100. Try: set_volume(75)")
```

✅ Preserve original errors:
```python
except Exception as e:
    raise AudioDeviceInUseError(device_id=3, original_error=str(e)) from e
```

✅ Log technical details, show user-friendly messages:
```python
logger.error(f"Failed to load {path}: {e.technical_message}")
self.notify(e.user_message)
```

### DON'T

❌ Use generic exceptions for user-facing errors:
```python
raise RuntimeError("Something failed")  # Bad
```

❌ Lose error context:
```python
except Exception as e:
    raise RuntimeError("Failed")  # Lost original error!
```

❌ Show technical details to users:
```python
self.notify(f"RuntimeError in line 42: {traceback}")  # TMI!
```

❌ Swallow errors silently:
```python
except Exception:
    pass  # Never do this!
```

## Architecture: The Three-Layer Model

```
┌─────────────────────────────────────────┐
│  USER LAYER (CLI/TUI)               │
│  - Formats error.user_message       │
│  - Shows error.recovery_hint        │
│  - Logs to file with --debug        │
└─────────────────────────────────────────┘
                  ↑
                  │ LaunchSamplerError
                  │
┌─────────────────────────────────────────┐
│  APPLICATION LAYER (Services)       │
│  - Catches low-level exceptions     │
│  - Converts to LaunchSamplerError   │
│  - Adds context and recovery hints  │
└─────────────────────────────────────────┘
                  ↑
                  │ Exception, OSError, etc.
                  │
┌─────────────────────────────────────────┐
│  LOW LEVEL (Audio, MIDI, I/O)       │
│  - Raises standard Python exceptions│
│  - Library-specific error codes     │
└─────────────────────────────────────────┘
```

**Key insight:** Each layer translates errors to be more useful at the next level up.
"""

import logging
from typing import Callable, TypeVar, Optional

from functools import wraps

from .base import LaunchSamplerError
from .audio import AudioDeviceError, AudioDeviceInUseError, AudioDeviceNotFoundError
from .config import ConfigFileInvalidError, ConfigValidationError


logger = logging.getLogger(__name__)

T = TypeVar('T')


def handle_errors(
    *,
    operation_name: str,
    user_notification: Optional[Callable[[str], None]] = None,
    fallback_value: Optional[T] = None,
    re_raise: bool = True,
    log_level: int = logging.ERROR
) -> Callable:
    """
    Decorator for consistent error handling.

    This provides a standard pattern for:
    - Logging errors with context
    - Showing user notifications
    - Returning fallback values
    - Re-raising or swallowing exceptions

    Args:
        operation_name: Name of the operation for logging (e.g., "load sample")
        user_notification: Optional callback to notify user (e.g., self.notify)
        fallback_value: Value to return if error occurs and re_raise=False
        re_raise: Whether to re-raise the exception after handling
        log_level: Logging level for the error (default: ERROR)

    Example:
        ```python
        @handle_errors(
            operation_name="load sample",
            user_notification=self.notify,
            re_raise=False,
            fallback_value=None
        )
        def load_sample(self, path: str):
            # If this raises, it will be logged and user notified
            return AudioData.from_file(path)
        ```

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)

            except LaunchSamplerError as e:
                # Our custom exceptions have user/technical messages
                logger.log(log_level, f"Failed to {operation_name}: {e.technical_message}")

                if user_notification:
                    user_notification(e.get_full_message())

                if re_raise:
                    raise
                return fallback_value

            except Exception as e:
                # Unexpected exceptions
                logger.log(
                    log_level,
                    f"Unexpected error during {operation_name}: {e}",
                    exc_info=True
                )

                if user_notification:
                    user_notification(f"Error: {e}")

                if re_raise:
                    raise
                return fallback_value

        return wrapper
    return decorator


class ErrorContext:
    """
    Context manager for error handling with automatic logging.

    Use this for critical sections where you want consistent error handling.

    Example:
        ```python
        with ErrorContext("initialize audio device") as ctx:
            device = AudioDevice()
            device.start()

        if ctx.error:
            print(f"Failed: {ctx.error}")
        ```
    """

    def __init__(
        self,
        operation: str,
        logger_instance: Optional[logging.Logger] = None,
        re_raise: bool = True
    ):
        """
        Initialize error context.

        Args:
            operation: Description of the operation
            logger_instance: Logger to use (defaults to module logger)
            re_raise: Whether to re-raise exceptions
        """
        self.operation = operation
        self.logger = logger_instance or logger
        self.re_raise = re_raise
        self.error: Optional[Exception] = None

    def __enter__(self):
        """Enter the context."""
        self.logger.debug(f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context and handle any exceptions.

        Returns:
            True if exception should be suppressed, False otherwise
        """
        if exc_type is None:
            self.logger.debug(f"Completed: {self.operation}")
            return False

        self.error = exc_val

        if isinstance(exc_val, LaunchSamplerError):
            self.logger.error(
                f"Failed to {self.operation}: {exc_val.technical_message}"
            )
        else:
            self.logger.error(
                f"Failed to {self.operation}: {exc_val}",
                exc_info=True
            )

        # Return True to suppress exception, False to re-raise
        return not self.re_raise


def wrap_pydantic_error(error: Exception, file_path: str) -> LaunchSamplerError:
    """
    Convert Pydantic validation errors to LaunchSampler exceptions.

    This maps validation errors from Pydantic (used for config validation)
    to our custom exception types with user-friendly messages.

    Args:
        error: The Pydantic ValidationError
        file_path: Path to the config file that failed validation

    Returns:
        A ConfigurationError with appropriate type and message
    """
    from pydantic import ValidationError

    error_msg = str(error)

    # Check if it's a JSON parse error (invalid syntax)
    if "Invalid JSON" in error_msg or "json_invalid" in error_msg:
        # Extract the actual parse error from Pydantic's message
        # Format: "Invalid JSON: <actual error> [type=json_invalid, ..."
        if "Invalid JSON:" in error_msg:
            parse_error = error_msg.split("Invalid JSON:")[1].split("[type=")[0].strip()
        else:
            parse_error = error_msg

        return ConfigFileInvalidError(file_path, parse_error)

    # It's a validation error (valid JSON but invalid values)
    # For Pydantic v2, use the error() method to get structured error info
    if isinstance(error, ValidationError):
        errors = error.errors()
        if errors:
            # If multiple errors, combine them into a comprehensive message
            if len(errors) == 1:
                # Single error - use simple message
                first_error = errors[0]
                field = ".".join(str(loc) for loc in first_error.get('loc', ('unknown',)))
                reason = first_error.get('msg', 'validation failed')
                value = first_error.get('input', None)

                return ConfigValidationError(
                    field=field,
                    value=value,
                    error_msg=reason,
                    file_path=file_path
                )
            else:
                # Multiple errors - show all of them
                error_lines = []
                for err in errors:
                    field = ".".join(str(loc) for loc in err.get('loc', ('unknown',)))
                    msg = err.get('msg', 'validation failed')
                    error_lines.append(f"  - {field}: {msg}")

                combined_msg = f"{len(errors)} validation errors:\n" + "\n".join(error_lines)

                return ConfigValidationError(
                    field="multiple fields",
                    value=None,
                    error_msg=combined_msg,
                    file_path=file_path
                )

    # Fallback: parse string representation
    lines = error_msg.split("\n")
    field = "unknown"
    reason = error_msg

    for line in lines:
        if "Field required" in line or "validation error" in line:
            # Extract field name from error format
            parts = line.split()
            if parts:
                field = parts[0] if parts else "unknown"
            reason = line
            break

    return ConfigValidationError(
        field=field,
        value=None,
        error_msg=reason,
        file_path=file_path
    )


def wrap_audio_device_error(error: Exception, device_id: Optional[int] = None) -> LaunchSamplerError:
    """
    Convert low-level audio errors to LaunchSampler exceptions.

    This maps error codes from audio libraries (PortAudio, sounddevice)
    to our custom exception types with user-friendly messages.

    Args:
        error: The original exception from the audio library
        device_id: The device ID involved in the error

    Returns:
        A LaunchSamplerError with appropriate type and message
    """
    error_msg = str(error)

    # Check for device-in-use error
    if "PaErrorCode -9996" in error_msg or "Invalid device" in error_msg:
        return AudioDeviceInUseError(device_id=device_id, original_error=error_msg)

    # Check for device not found
    if "device" in error_msg.lower() and "not found" in error_msg.lower():
        if device_id is not None:
            return AudioDeviceNotFoundError(device_id)

    # Generic audio device error
    return AudioDeviceError(
        user_message=f"Audio device error: {error_msg}",
        technical_message=f"Audio device {device_id} error: {error_msg}",
        device_id=device_id
    )


def format_error_for_display(error: Exception) -> tuple[str, Optional[str]]:
    """
    Format an exception for user display.

    Returns a tuple of (message, recovery_hint).

    Args:
        error: The exception to format

    Returns:
        Tuple of (user_message, recovery_hint or None)
    """
    if isinstance(error, LaunchSamplerError):
        return error.user_message, error.recovery_hint

    # For standard exceptions, create a user-friendly message
    error_type = type(error).__name__
    return f"{error_type}: {error}", None


def collect_errors(operation: str) -> "ErrorCollector":
    """
    Create an error collector for batch operations.

    Use this when you want to attempt multiple operations and collect
    all errors before reporting them.

    Example:
        ```python
        collector = collect_errors("load samples")

        for file in files:
            with collector.try_operation(f"load {file}"):
                load_sample(file)

        if collector.has_errors:
            print(f"Failed to load {collector.error_count} samples:")
            for error in collector.errors:
                print(f"  - {error}")
        ```

    Args:
        operation: Description of the overall operation

    Returns:
        ErrorCollector instance
    """
    return ErrorCollector(operation)


class ErrorCollector:
    """
    Collects multiple errors during batch operations.

    Allows operations to continue even if some fail, then
    report all failures at once.
    """

    def __init__(self, operation: str):
        """
        Initialize error collector.

        Args:
            operation: Description of the overall operation
        """
        self.operation = operation
        self.errors: list[tuple[str, Exception]] = []
        self.success_count = 0

    @property
    def has_errors(self) -> bool:
        """Check if any errors were collected."""
        return len(self.errors) > 0

    @property
    def error_count(self) -> int:
        """Get the number of errors collected."""
        return len(self.errors)

    def try_operation(self, sub_operation: str):
        """
        Context manager for a single operation within the batch.

        Args:
            sub_operation: Description of this specific operation

        Returns:
            Context manager that catches and stores errors
        """
        return self._OperationContext(self, sub_operation)

    def get_summary(self) -> str:
        """
        Get a summary of collected errors.

        Returns:
            Multi-line summary string
        """
        if not self.has_errors:
            return f"All operations completed successfully ({self.success_count} total)"

        summary = f"Failed {self.error_count} of {self.error_count + self.success_count} operations:\n"
        for sub_op, error in self.errors:
            if isinstance(error, LaunchSamplerError):
                summary += f"  - {sub_op}: {error.user_message}\n"
            else:
                summary += f"  - {sub_op}: {error}\n"

        return summary.rstrip()

    class _OperationContext:
        """Internal context manager for individual operations."""

        def __init__(self, collector: "ErrorCollector", sub_operation: str):
            self.collector = collector
            self.sub_operation = sub_operation

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.collector.success_count += 1
                return False

            # Store the error
            self.collector.errors.append((self.sub_operation, exc_val))

            # Suppress the exception (don't re-raise)
            return True
