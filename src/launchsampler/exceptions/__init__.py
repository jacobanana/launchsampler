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

See `launchsampler.exceptions.handlers` for utilities to handle these exceptions systematically.
"""

from .base import LaunchSamplerError
from .audio import AudioDeviceError, AudioDeviceInUseError, AudioDeviceNotFoundError
from .config import ConfigurationError, ConfigFileInvalidError, ConfigValidationError
from .handlers import (
    handle_errors,
    ErrorContext,
    ErrorCollector,
    wrap_pydantic_error,
    wrap_audio_device_error,
    format_error_for_display,
    collect_errors,
)

__all__ = [
    # Base
    "LaunchSamplerError",
    # Audio
    "AudioDeviceError",
    "AudioDeviceInUseError",
    "AudioDeviceNotFoundError",
    # Config
    "ConfigurationError",
    "ConfigFileInvalidError",
    "ConfigValidationError",
    # Handlers
    "handle_errors",
    "ErrorContext",
    "ErrorCollector",
    "wrap_pydantic_error",
    "wrap_audio_device_error",
    "format_error_for_display",
    "collect_errors",
]
