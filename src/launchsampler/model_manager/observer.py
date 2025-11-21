"""Generic observer pattern manager.

This module provides a reusable ObserverManager class that handles thread-safe
registration, unregistration, and notification of observers. It eliminates the
need to duplicate observer management code across multiple classes.
"""

import logging
from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for the observer protocol
# Bound to Any to indicate it can be any observer type
T = TypeVar("T", bound=object)


class ObserverManager[T: object]:
    """
    Generic observer list manager with thread-safe registration and notification.

    This class provides a reusable implementation of the observer pattern,
    eliminating code duplication across EditorService, Player, LaunchpadController,
    SamplerStateMachine, and other classes.

    Type Parameters:
        T: The observer protocol type (e.g., EditObserver, StateObserver)

    Thread Safety:
        All operations are thread-safe. The lock is released before calling
        observer callbacks to prevent potential deadlocks.

    Example:
        ```python
        class MyService:
            def __init__(self):
                self._observers = ObserverManager[MyObserver]()

            def register_observer(self, observer: MyObserver) -> None:
                self._observers.register(observer)

            def unregister_observer(self, observer: MyObserver) -> None:
                self._observers.unregister(observer)

            def _notify_something_happened(self, data):
                self._observers.notify('on_something_happened', data)
        ```
    """

    def __init__(self, lock: Lock | None = None, observer_type_name: str = "observer"):
        """
        Initialize the observer manager.

        Args:
            lock: Optional threading lock to use. If None, creates a new lock.
            observer_type_name: Name of the observer type for logging (e.g., "edit", "state")
        """
        self._observers: list[T] = []
        self._lock = lock or Lock()
        self._observer_type_name = observer_type_name

    def register(self, observer: T) -> None:
        """
        Register an observer (idempotent - won't add duplicates).

        Args:
            observer: The observer to register

        Thread Safety:
            Safe to call from any thread.
        """
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
                logger.info(f"Registered {self._observer_type_name} observer: {observer}")
            else:
                logger.debug(f"{self._observer_type_name} observer already registered: {observer}")

    def unregister(self, observer: T) -> None:
        """
        Unregister an observer.

        Args:
            observer: The observer to unregister

        Thread Safety:
            Safe to call from any thread.
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
                logger.debug(f"Unregistered {self._observer_type_name} observer: {observer}")
            else:
                logger.warning(
                    f"Attempted to unregister unknown {self._observer_type_name} observer: {observer}"
                )

    def notify(self, callback_name: str, *args: Any, **kwargs: Any) -> None:
        """
        Notify all observers by calling their callback method.

        The lock is acquired to copy the observer list, then released before
        calling callbacks. This prevents deadlocks if observers try to register/
        unregister during notification.

        Args:
            callback_name: Name of the callback method to call (e.g., 'on_edit_event')
            *args: Positional arguments to pass to the callback
            **kwargs: Keyword arguments to pass to the callback

        Thread Safety:
            Safe to call from any thread. Lock is released before callbacks.

        Error Handling:
            Exceptions in observer callbacks are logged but don't affect other observers.
        """
        # Copy observer list while holding lock
        with self._lock:
            observers = list(self._observers)

        # Call observers without holding lock (prevents deadlocks)
        for observer in observers:
            try:
                callback = getattr(observer, callback_name)
                callback(*args, **kwargs)
            except AttributeError:
                logger.error(
                    f"{self._observer_type_name} observer {observer} has no method '{callback_name}'",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Error notifying {self._observer_type_name} observer {observer} via {callback_name}: {e}",
                    exc_info=True,
                )

    def notify_with_filter(
        self, callback_name: str, filter_fn: Callable[[T], bool], *args: Any, **kwargs: Any
    ) -> None:
        """
        Notify only observers that match the filter predicate.

        Args:
            callback_name: Name of the callback method to call
            filter_fn: Predicate function that returns True for observers to notify
            *args: Positional arguments to pass to the callback
            **kwargs: Keyword arguments to pass to the callback

        Thread Safety:
            Safe to call from any thread. Lock is released before callbacks.

        Example:
            ```python
            # Only notify observers that implement a specific interface
            self._observers.notify_with_filter(
                'on_custom_event',
                lambda obs: hasattr(obs, 'supports_custom_events'),
                event_data
            )
            ```
        """
        # Copy observer list while holding lock
        with self._lock:
            observers = [obs for obs in self._observers if filter_fn(obs)]

        # Call filtered observers without holding lock
        for observer in observers:
            try:
                callback = getattr(observer, callback_name)
                callback(*args, **kwargs)
            except AttributeError:
                logger.error(
                    f"{self._observer_type_name} observer {observer} has no method '{callback_name}'",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Error notifying {self._observer_type_name} observer {observer} via {callback_name}: {e}",
                    exc_info=True,
                )

    def count(self) -> int:
        """
        Get the number of registered observers.

        Returns:
            Number of observers currently registered

        Thread Safety:
            Safe to call from any thread.
        """
        with self._lock:
            return len(self._observers)

    def has_observers(self) -> bool:
        """
        Check if any observers are registered.

        Returns:
            True if at least one observer is registered, False otherwise

        Thread Safety:
            Safe to call from any thread.
        """
        with self._lock:
            return len(self._observers) > 0

    def clear(self) -> None:
        """
        Remove all registered observers.

        Thread Safety:
            Safe to call from any thread.
        """
        with self._lock:
            count = len(self._observers)
            self._observers.clear()
            if count > 0:
                logger.info(f"Cleared {count} {self._observer_type_name} observer(s)")

    def __contains__(self, observer: T) -> bool:
        """
        Check if an observer is registered (supports 'in' operator).

        Args:
            observer: The observer to check for

        Returns:
            True if observer is registered, False otherwise

        Thread Safety:
            Safe to call from any thread.

        Example:
            ```python
            if my_observer in observer_manager:
                print("Observer is registered")
            ```
        """
        with self._lock:
            return observer in self._observers

    def __len__(self) -> int:
        """
        Get the number of registered observers (supports len() function).

        Returns:
            Number of observers currently registered

        Thread Safety:
            Safe to call from any thread.

        Example:
            ```python
            print(f"There are {len(observer_manager)} observers")
            ```
        """
        with self._lock:
            return len(self._observers)

    def __bool__(self) -> bool:
        """
        Check if any observers are registered (supports bool() and if checks).

        Returns:
            True if at least one observer is registered, False otherwise

        Thread Safety:
            Safe to call from any thread.

        Example:
            ```python
            if observer_manager:
                print("Has observers")
            ```
        """
        with self._lock:
            return len(self._observers) > 0
