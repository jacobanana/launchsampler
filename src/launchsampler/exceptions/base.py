"""Base exception class for LaunchSampler.

All custom exceptions inherit from LaunchSamplerError to allow catching
all app-specific errors in one place. The base class provides:

- `user_message`: Human-friendly message for display to users
- `technical_message`: Detailed message for logging
- `recoverable`: Whether the error can be recovered from
- `recovery_hint`: Optional suggestion for how to fix the issue
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
