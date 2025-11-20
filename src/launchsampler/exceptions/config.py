"""Configuration-related exceptions.

This module defines exceptions for configuration errors:
- ConfigurationError: Base class for configuration errors
- ConfigFileInvalidError: Config file has invalid syntax
- ConfigValidationError: Config values fail validation
"""

from .base import LaunchSamplerError


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
