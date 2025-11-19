"""
Centralized error handling utilities.

This module provides a systematic, layered approach to error handling:

1. **Custom Exceptions** - Typed, user-friendly error classes (see `launchsampler.exceptions`)
2. **Error Context** - Preserve technical details for logging, show friendly messages to users
3. **Recovery Hints** - Tell users what to do when things fail
4. **Error Isolation** - One failure shouldn't cascade to others

## Quick Reference

### When to Use What

| Scenario | Use This | Example |
|----------|----------|---------|
| User-facing error (invalid input) | `ValidationError` | `raise ValidationError("pad_index", 99, "must be 0-63")` |
| Audio device fails | `AudioDeviceError` subclass | `raise AudioDeviceInUseError(device_id=3)` |
| Sample file problem | `AudioLoadError` | `raise AudioLoadError(path, "file not found")` |
| MIDI device missing | `MidiDeviceNotFoundError` | `raise MidiDeviceNotFoundError("Launchpad Mini")` |
| Operation on empty pad | `EmptyPadError` | `raise EmptyPadError(pad_index=5, operation="play")` |

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
from launchsampler.utils.error_handler import wrap_audio_device_error

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

### Example 2: Editor Operations with User Notifications

```python
from launchsampler.utils.error_handler import handle_errors
from launchsampler.exceptions import EmptyPadError

@handle_errors(
    operation_name="delete pad",
    user_notification=lambda msg: self.notify(msg, severity="error"),
    re_raise=False
)
def action_delete_pad(self) -> None:
    '''Delete sample from selected pad.'''
    if self.selected_pad_index is None:
        return

    pad = self.editor.get_pad(self.selected_pad_index)
    if not pad.is_assigned:
        raise EmptyPadError(self.selected_pad_index, "delete")

    self.editor.clear_pad(self.selected_pad_index)
```

Benefits:
- Automatic logging with operation context
- User gets recovery hint automatically
- Less boilerplate

### Example 3: Batch Operations (Loading Multiple Samples)

```python
from launchsampler.utils.error_handler import collect_errors

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
from launchsampler.utils.error_handler import ErrorContext

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
except OSError as e:
    raise AudioLoadError(path, str(e)) from e
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
from typing import Callable, TypeVar, Optional, Any
from functools import wraps

from launchsampler.exceptions import LaunchSamplerError


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
    from launchsampler.exceptions import (
        AudioDeviceInUseError,
        AudioDeviceError
    )

    error_msg = str(error)

    # Check for device-in-use error
    if "PaErrorCode -9996" in error_msg or "Invalid device" in error_msg:
        return AudioDeviceInUseError(device_id=device_id, original_error=error_msg)

    # Check for device not found
    if "device" in error_msg.lower() and "not found" in error_msg.lower():
        from launchsampler.exceptions import AudioDeviceNotFoundError
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
