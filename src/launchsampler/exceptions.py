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
└── ConfigurationError
    ├── ConfigFileInvalidError
    └── ConfigValidationError
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

### Example: Config Validation Error

```python
from launchsampler.exceptions import ConfigValidationError

# Raise when config value is invalid
raise ConfigValidationError(
    field="panic_button_cc_value",
    value="hunder",
    error_msg="Input should be a valid integer",
    file_path="/path/to/config.json"
)

# User sees: "Invalid configuration value for 'panic_button_cc_value': Input should be a valid integer"
# Recovery hint: "Update the 'panic_button_cc_value' value in your configuration\nConfig file: /path/to/config.json"
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


# Configuration errors

class ConfigurationError(LaunchSamplerError):
    """Configuration is invalid or cannot be loaded."""
    pass


class ConfigFileInvalidError(ConfigurationError):
    """Configuration file has invalid JSON or YAML syntax."""

    def __init__(self, file_path: str, parse_error: str):
        """
        Initialize config file invalid error.

        Args:
            file_path: Path to the invalid config file
            parse_error: The parsing error message
        """
        # Extract helpful info from parse error
        user_msg = f"Configuration file has invalid syntax"
        recovery = "Check for common JSON errors:\n"
        recovery += "  - Trailing commas (remove commas after last item)\n"
        recovery += "  - Missing quotes around strings\n"
        recovery += "  - Unclosed braces or brackets\n"
        recovery += f"  - Edit: {file_path}"

        # Check for specific common errors
        if "trailing comma" in parse_error.lower():
            user_msg = "Configuration file has a trailing comma"
            recovery = (
                f"Remove the trailing comma from {file_path}\n"
                "JSON doesn't allow commas after the last item in an object or array"
            )
        elif "expecting" in parse_error.lower():
            user_msg = "Configuration file has a syntax error"

        super().__init__(
            user_message=user_msg,
            technical_message=f"JSON parse error in {file_path}: {parse_error}",
            recoverable=True,
            recovery_hint=recovery
        )
        self.file_path = file_path
        self.parse_error = parse_error


class ConfigValidationError(ConfigurationError):
    """Configuration values fail validation."""

    def __init__(self, field: str, value: any, error_msg: str, file_path: str = None):
        """
        Initialize config validation error.

        Args:
            field: The configuration field that failed validation
            value: The invalid value
            error_msg: Why the value is invalid
            file_path: Path to the config file (optional)
        """
        user_msg = f"Invalid configuration value for '{field}': {error_msg}"

        recovery = f"Update the '{field}' value in your configuration"
        if file_path:
            recovery += f"\nConfig file: {file_path}"

        # Add specific recovery hints for common fields
        if "audio_device" in field.lower():
            recovery += "\nRun 'launchsampler audio list' to see valid device IDs"
        elif "buffer" in field.lower():
            recovery += "\nValid buffer sizes: 128, 256, 512, 1024, 2048"
        elif "midi" in field.lower():
            recovery += "\nRun 'launchsampler midi list' to see valid MIDI devices"

        super().__init__(
            user_message=user_msg,
            technical_message=f"Config validation failed for {field}={value}: {error_msg}",
            recoverable=True,
            recovery_hint=recovery
        )
        self.field = field
        self.value = value
        self.file_path = file_path
