"""Audio-related exceptions.

This module defines exceptions for audio device errors:
- AudioDeviceError: Base class for audio device errors
- AudioDeviceInUseError: Device is already in use
- AudioDeviceNotFoundError: Device was not found
"""

from .base import LaunchSamplerError


class AudioDeviceError(LaunchSamplerError):
    """Audio device initialization or operation failed."""

    def __init__(self, user_message: str, device_id: int | None = None, **kwargs):
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

    def __init__(self, device_id: int | None = None, original_error: str | None = None):
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
            recovery_hint=recovery,
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
            user_message=user_msg, device_id=device_id, recoverable=True, recovery_hint=recovery
        )
