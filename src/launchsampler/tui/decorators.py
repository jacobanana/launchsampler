"""Decorators for TUI components."""

from functools import wraps
from launchsampler.exceptions import handle_errors as _handle_errors


def require_mode(*modes):
    """Decorator to restrict action to specific sampler mode(s).

    Args:
        *modes: One or more mode names (e.g., "edit", "play")

    If the app is not in one of the specified modes, the decorated
    method will return immediately without executing.

    Example:
        @require_mode("edit")
        def action_copy_pad(self):
            ...

        @require_mode("edit", "play")
        def action_save(self):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self._sampler_mode not in modes:
                return
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def handle_action_errors(operation_name: str):
    """
    Decorator for TUI action methods that wraps the centralized error handler.

    This is a TUI-specific wrapper around the centralized error handler that:
    - Uses self.notify for user notifications
    - Doesn't re-raise exceptions (keeps TUI responsive)
    - Returns None on error

    Example:
        @handle_action_errors("cut pad")
        def action_cut_pad(self):
            ...
    """
    def decorator(func):
        # Get the method's self instance
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Create the error handler with TUI-specific settings
            handler = _handle_errors(
                operation_name=operation_name,
                user_notification=lambda msg: self.notify(msg, severity="error", timeout=5),
                re_raise=False,
                fallback_value=None
            )
            # Apply the handler and call the function
            wrapped = handler(func)
            return wrapped(self, *args, **kwargs)
        return wrapper
    return decorator


# Convenient mode restriction aliases
edit_only = require_mode("edit")
play_only = require_mode("play")
