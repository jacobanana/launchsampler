"""Decorators for TUI components."""

from functools import wraps


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


# Convenient mode restriction aliases
edit_only = require_mode("edit")
play_only = require_mode("play")
