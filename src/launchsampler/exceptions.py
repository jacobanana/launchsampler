"""
Custom exception hierarchy for LaunchSampler.

This module defines application-specific exceptions that provide:
- Clear error categories (audio, device, validation, etc.)
- User-friendly messages
- Context preservation
- Recovery hints

## Exception Hierarchy

```
LaunchSamplerError (base)
├── AudioDeviceError
│   ├── AudioDeviceInUseError
│   └── AudioDeviceNotFoundError
├── AudioLoadError
├── SampleError
├── PadError
│   └── EmptyPadError
├── ConfigurationError
├── MidiError
│   └── MidiDeviceNotFoundError
└── ValidationError
```

## Usage

All custom exceptions inherit from `LaunchSamplerError`, which provides:

- `user_message`: Human-friendly message for display to users
- `technical_message`: Detailed message for logging
- `recoverable`: Whether the error can be recovered from
- `recovery_hint`: Optional suggestion for how to fix the issue

### Example: Audio Device In Use

```python
from launchsampler.exceptions import AudioDeviceInUseError

# Raise when device is already in use
raise AudioDeviceInUseError(device_id=3, original_error="PaErrorCode -9996")

# User sees: "Audio device is already in use by another application."
# Recovery hint: "Please close other instances... Run 'launchsampler audio list'..."
# Logs show: Technical details including original error
```

### Example: Empty Pad Operation

```python
from launchsampler.exceptions import EmptyPadError

# Raise when trying to operate on empty pad
raise EmptyPadError(pad_index=5, operation="delete")

# User sees: "Cannot delete on empty pad 5"
# Recovery hint: "Assign a sample to the pad first."
```

### Example: Validation Error

```python
from launchsampler.exceptions import ValidationError

# Raise when input validation fails
raise ValidationError("volume", 150, "must be 0-100")

# User sees: "Invalid volume: must be 0-100"
```

## Best Practices

1. **Always use specific exception types** rather than generic `RuntimeError`
2. **Provide recovery hints** to help users fix the problem
3. **Preserve original exceptions** using `from e` when re-raising
4. **Separate user vs technical messages** for better UX and debugging

See `launchsampler.utils.error_handler` for utilities to handle these exceptions systematically.
"""

from typing import Optional


class LaunchSamplerError(Exception):
    """
    Base exception for all LaunchSampler errors.

    All custom exceptions inherit from this to allow catching
    all app-specific errors in one place.

    Attributes:
        user_message: Human-friendly message for display
        technical_message: Detailed message for logging
        recoverable: Whether the error can be recovered from
        recovery_hint: Optional hint for how to fix the issue
    """

    def __init__(
        self,
        user_message: str,
        technical_message: Optional[str] = None,
        recoverable: bool = False,
        recovery_hint: Optional[str] = None,
        *args,
        **kwargs
    ):
        """
        Initialize a LaunchSampler error.

        Args:
            user_message: Message to show to users
            technical_message: Detailed message for logs (defaults to user_message)
            recoverable: True if operation can be retried/recovered
            recovery_hint: Suggestion for how to fix the issue
        """
        super().__init__(user_message, *args, **kwargs)
        self.user_message = user_message
        self.technical_message = technical_message or user_message
        self.recoverable = recoverable
        self.recovery_hint = recovery_hint

    def __str__(self) -> str:
        """Return user-friendly message."""
        return self.user_message

    def get_full_message(self) -> str:
        """Get complete error message with recovery hint."""
        msg = self.user_message
        if self.recovery_hint:
            msg += f"\n\nSuggestion: {self.recovery_hint}"
        return msg


# Audio-related errors

class AudioDeviceError(LaunchSamplerError):
    """Audio device initialization or operation failed."""

    def __init__(
        self,
        user_message: str,
        device_id: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize audio device error.

        Args:
            user_message: User-friendly error message
            device_id: The device ID that failed (if applicable)
        """
        super().__init__(user_message, **kwargs)
        self.device_id = device_id


class AudioDeviceInUseError(AudioDeviceError):
    """Audio device is already in use by another application."""

    def __init__(self, device_id: Optional[int] = None, original_error: Optional[str] = None):
        """
        Initialize device-in-use error.

        Args:
            device_id: The device ID that's in use
            original_error: The original error message from the audio library
        """
        user_msg = "Audio device is already in use by another application."
        tech_msg = user_msg
        if original_error:
            tech_msg += f"\nOriginal error: {original_error}"

        recovery = (
            "Please close other instances of LaunchSampler or other audio applications. "
            "Run 'launchsampler audio list' to see available devices."
        )

        super().__init__(
            user_message=user_msg,
            technical_message=tech_msg,
            device_id=device_id,
            recoverable=True,
            recovery_hint=recovery
        )


class AudioDeviceNotFoundError(AudioDeviceError):
    """Requested audio device was not found."""

    def __init__(self, device_id: int):
        """
        Initialize device-not-found error.

        Args:
            device_id: The device ID that wasn't found
        """
        user_msg = f"Audio device {device_id} not found."
        recovery = "Run 'launchsampler audio list' to see available devices."

        super().__init__(
            user_message=user_msg,
            device_id=device_id,
            recoverable=True,
            recovery_hint=recovery
        )


class AudioLoadError(LaunchSamplerError):
    """Failed to load audio file."""

    def __init__(self, file_path: str, reason: str):
        """
        Initialize audio load error.

        Args:
            file_path: Path to the file that failed to load
            reason: Why the file couldn't be loaded
        """
        user_msg = f"Failed to load audio file: {reason}"
        tech_msg = f"Failed to load {file_path}: {reason}"

        super().__init__(
            user_message=user_msg,
            technical_message=tech_msg,
            recoverable=False
        )
        self.file_path = file_path


# Sample/Pad operation errors

class SampleError(LaunchSamplerError):
    """Sample-related operation failed."""
    pass


class PadError(LaunchSamplerError):
    """Pad-related operation failed."""

    def __init__(self, user_message: str, pad_index: Optional[int] = None, **kwargs):
        """
        Initialize pad error.

        Args:
            user_message: User-friendly error message
            pad_index: The pad index that had the error
        """
        super().__init__(user_message, **kwargs)
        self.pad_index = pad_index


class EmptyPadError(PadError):
    """Operation attempted on an empty pad that requires a sample."""

    def __init__(self, pad_index: int, operation: str):
        """
        Initialize empty pad error.

        Args:
            pad_index: The empty pad index
            operation: The operation that was attempted
        """
        user_msg = f"Cannot {operation} on empty pad {pad_index}"
        recovery = "Assign a sample to the pad first."

        super().__init__(
            user_message=user_msg,
            pad_index=pad_index,
            recoverable=True,
            recovery_hint=recovery
        )


# Configuration errors

class ConfigurationError(LaunchSamplerError):
    """Configuration is invalid or cannot be loaded."""
    pass


# MIDI errors

class MidiError(LaunchSamplerError):
    """MIDI device or operation error."""
    pass


class MidiDeviceNotFoundError(MidiError):
    """MIDI device not found."""

    def __init__(self, device_name: Optional[str] = None):
        """
        Initialize MIDI device not found error.

        Args:
            device_name: Name of the device that wasn't found
        """
        if device_name:
            user_msg = f"MIDI device '{device_name}' not found."
        else:
            user_msg = "No MIDI device found."

        recovery = "Run 'launchsampler midi list' to see available MIDI devices."

        super().__init__(
            user_message=user_msg,
            recoverable=True,
            recovery_hint=recovery
        )


# Validation errors

class ValidationError(LaunchSamplerError):
    """Input validation failed."""

    def __init__(self, field: str, value, reason: str):
        """
        Initialize validation error.

        Args:
            field: The field that failed validation
            value: The invalid value
            reason: Why the value is invalid
        """
        user_msg = f"Invalid {field}: {reason}"
        tech_msg = f"Validation failed for {field}={value}: {reason}"

        super().__init__(
            user_message=user_msg,
            technical_message=tech_msg,
            recoverable=True
        )
        self.field = field
        self.value = value
