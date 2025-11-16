"""Editor service for managing Launchpad editing operations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from launchsampler.models import Launchpad, Pad, Sample, Set, AppConfig, PlaybackMode
from launchsampler.protocols import EditEvent, EditObserver
from launchsampler.utils import ObserverManager

logger = logging.getLogger(__name__)


class EditorService:
    """
    Manages editing operations on a Launchpad configuration.

    This service encapsulates all business logic for editing pads,
    managing samples, and saving/loading sets. It operates directly
    on a Launchpad instance, with no dependency on the full app.

    Event-Driven Architecture:
        All editing operations emit EditEvent notifications to registered
        observers. This ensures automatic synchronization of audio engine
        and UI without manual coordination.

    Threading:
        All methods are called from the UI thread (Textual's main loop).
        Observer notifications are also dispatched on the UI thread.
        The _event_lock protects the observer list during registration,
        but is released before calling observers to avoid holding locks
        during potentially slow callbacks.

    Dependency Injection:
        EditorService receives a Launchpad reference, not the entire app.
        This eliminates circular dependencies and improves testability.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the editor service.

        Args:
            config: Application configuration
        """
        self._launchpad = None
        self.config = config
        self._clipboard: Optional[Pad] = None

        # Event system
        self._observers = ObserverManager[EditObserver](observer_type_name="edit")
        logger.info("EditorService initialized")

    @property
    def launchpad(self) -> Launchpad:
        """Get the launchpad being edited."""
        return self._launchpad

    def update_launchpad(self, launchpad: Launchpad) -> None:
        """
        Update the launchpad reference.

        This should be called when a new set is mounted to ensure
        the editor is working with the correct launchpad instance.

        Args:
            launchpad: The new Launchpad instance to edit
        """
        self._launchpad = launchpad
        logger.debug("EditorService launchpad reference updated")

    @property
    def grid_size(self) -> int:
        """Get the total number of pads in the launchpad grid."""
        return len(self.launchpad.pads)

    @property
    def has_clipboard(self) -> bool:
        """Check if clipboard has content."""
        return self._clipboard is not None

    # =================================================================
    # Event System
    # =================================================================

    def register_observer(self, observer: EditObserver) -> None:
        """
        Register an observer to receive edit events.

        Args:
            observer: Object implementing EditObserver protocol
        """
        self._observers.register(observer)

    def unregister_observer(self, observer: EditObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        self._observers.unregister(observer)

    def _notify_observers(
        self,
        event: EditEvent,
        pad_indices: list[int],
        pads: list[Pad]
    ) -> None:
        """
        Notify all registered observers of an edit event.

        Args:
            event: The editing event that occurred
            pad_indices: List of affected pad indices
            pads: List of affected pad states (post-edit)

        Note:
            ObserverManager handles exception catching and logging automatically.
        """
        self._observers.notify('on_edit_event', event, pad_indices, pads)

    # =================================================================
    # Validation
    # =================================================================

    def _validate_pad_index(self, pad_index: int, label: str = "Pad index") -> None:
        """
        Validate that a pad index is within valid range.

        Args:
            pad_index: The index to validate
            label: Description for error message (e.g., "Source pad index")

        Raises:
            IndexError: If pad_index is out of range
        """
        if not 0 <= pad_index < self.grid_size:
            raise IndexError(f"{label} {pad_index} out of range (0-{self.grid_size-1})")

    def get_pad(self, pad_index: int) -> Pad:
        """
        Get a pad by index (read-only).

        Args:
            pad_index: Index of pad to get

        Returns:
            The Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        self._validate_pad_index(pad_index)
        return self.launchpad.pads[pad_index]

    def assign_sample(self, pad_index: int, sample_path: Path) -> Pad:
        """
        Assign a sample to a pad.

        Args:
            pad_index: Index of pad to assign to
            sample_path: Path to audio file

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If sample file doesn't exist
        """
        self._validate_pad_index(pad_index)
        if not sample_path.exists():
            raise ValueError(f"Sample file not found: {sample_path}")

        # Create sample from file
        sample = Sample.from_file(sample_path)

        # Get pad and assign sample
        pad = self.launchpad.pads[pad_index]
        was_empty = not pad.is_assigned
        pad.sample = sample
        pad.volume = 0.8  # Default volume

        # Set default color if pad was previously empty
        if was_empty:
            pad.color = pad.mode.get_default_color()

        # Notify observers
        self._notify_observers(EditEvent.PAD_ASSIGNED, [pad_index], [pad])

        logger.info(f"Assigned sample '{sample.name}' to pad {pad_index}")
        return pad

    def clear_pad(self, pad_index: int) -> Pad:
        """
        Clear a pad (remove sample).

        Args:
            pad_index: Index of pad to clear

        Returns:
            The new empty Pad

        Raises:
            IndexError: If pad_index is out of range
        """
        self._validate_pad_index(pad_index)
        # Get current pad position
        old_pad = self.launchpad.pads[pad_index]

        # Replace with empty pad
        new_pad = Pad.empty(old_pad.x, old_pad.y)
        self.launchpad.pads[pad_index] = new_pad

        # Notify observers
        self._notify_observers(EditEvent.PAD_CLEARED, [pad_index], [new_pad])

        logger.info(f"Cleared pad {pad_index}")
        return new_pad

    def set_pad_mode(self, pad_index: int, mode: PlaybackMode) -> Pad:
        """
        Change the playback mode for a pad.

        Args:
            pad_index: Index of pad to modify
            mode: New playback mode

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad has no sample assigned
        """
        self._validate_pad_index(pad_index)
        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned:
            raise ValueError(f"Cannot set mode on empty pad {pad_index}")

        pad.mode = mode
        pad.color = mode.get_default_color()

        # Notify observers
        self._notify_observers(EditEvent.PAD_MODE_CHANGED, [pad_index], [pad])

        logger.info(f"Set pad {pad_index} mode to {mode.value}")
        return pad

    def set_pad_volume(self, pad_index: int, volume: float) -> Pad:
        """
        Set the volume for a pad.

        Args:
            pad_index: Index of pad to modify
            volume: New volume (0.0-1.0)

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If volume is out of range
        """
        self._validate_pad_index(pad_index)
        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume {volume} out of range (0.0-1.0)")

        pad = self.launchpad.pads[pad_index]
        pad.volume = volume

        # Notify observers
        self._notify_observers(EditEvent.PAD_VOLUME_CHANGED, [pad_index], [pad])

        logger.info(f"Set pad {pad_index} volume to {volume:.0%}")
        return pad

    def set_sample_name(self, pad_index: int, name: str) -> Pad:
        """
        Set the name for a pad's sample.

        Args:
            pad_index: Index of pad to modify
            name: New sample name

        Returns:
            The modified Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad has no sample assigned or name is empty
        """
        self._validate_pad_index(pad_index)
        if not name or not name.strip():
            raise ValueError("Sample name cannot be empty")

        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned or not pad.sample:
            raise ValueError(f"Cannot set name on empty pad {pad_index}")

        pad.sample.name = name.strip()

        # Notify observers
        self._notify_observers(EditEvent.PAD_NAME_CHANGED, [pad_index], [pad])

        logger.info(f"Set pad {pad_index} sample name to '{name}'")
        return pad

    def move_pad(self, source_index: int, target_index: int, swap: bool = False) -> tuple[Pad, Pad]:
        """
        Move a sample from source pad to target pad.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            swap: If True, swap samples between pads. If False, overwrite target.

        Returns:
            Tuple of (new source pad, new target pad)

        Raises:
            IndexError: If pad indices are out of range
            ValueError: If source pad is empty
        """
        self._validate_pad_index(source_index, "Source pad index")
        self._validate_pad_index(target_index, "Target pad index")
        if source_index == target_index:
            raise ValueError("Source and target pads must be different")

        source_pad = self.launchpad.pads[source_index]
        target_pad = self.launchpad.pads[target_index]
        logger.info(f"Moving sample from pad {source_index} to pad {target_index} (swap={swap})")

        if not source_pad.is_assigned:
            raise ValueError(f"Source pad {source_index} has no sample to move")

        if swap and target_pad.is_assigned:
            # Swap samples between pads
            # Store target pad data
            target_sample = target_pad.sample
            target_mode = target_pad.mode
            target_volume = target_pad.volume
            target_color = target_pad.color

            # Move source to target
            target_pad.sample = source_pad.sample
            target_pad.mode = source_pad.mode
            target_pad.volume = source_pad.volume
            target_pad.color = source_pad.color

            # Move target to source
            source_pad.sample = target_sample
            source_pad.mode = target_mode
            source_pad.volume = target_volume
            source_pad.color = target_color

            logger.info(f"Swapped pads {source_index} and {target_index}")
        else:
            # Move/overwrite: copy source to target and clear source
            target_pad.sample = source_pad.sample
            target_pad.mode = source_pad.mode
            target_pad.volume = source_pad.volume
            target_pad.color = source_pad.color

            # Clear source pad
            source_pos = (source_pad.x, source_pad.y)
            new_source = Pad.empty(source_pos[0], source_pos[1])
            self.launchpad.pads[source_index] = new_source
            source_pad = new_source

            logger.info(f"Moved sample from pad {source_index} to {target_index}")

        # Notify observers about both affected pads
        self._notify_observers(
            EditEvent.PAD_MOVED,
            [source_index, target_index],
            [source_pad, target_pad]
        )

        return (source_pad, target_pad)

    def duplicate_pad(self, source_index: int, target_index: int, overwrite: bool = False) -> Pad:
        """
        Duplicate a sample from source pad to target pad.

        Creates a complete deep copy of the source pad, preserving only
        the target's position. This ensures all properties are duplicated
        without needing to handle them individually.

        Args:
            source_index: Index of source pad
            target_index: Index of target pad
            overwrite: If False (default), raise ValueError if target already has a sample.
                      If True, replace target pad contents even if occupied.

        Returns:
            The new target Pad

        Raises:
            IndexError: If pad indices are out of range
            ValueError: If source pad is empty, indices are the same,
                       or target is occupied and overwrite=False
        """
        self._validate_pad_index(source_index, "Source pad index")
        self._validate_pad_index(target_index, "Target pad index")
        if source_index == target_index:
            raise ValueError("Source and target pads must be different")

        source_pad = self.launchpad.pads[source_index]
        target_pad = self.launchpad.pads[target_index]

        if not source_pad.is_assigned:
            raise ValueError(f"Source pad {source_index} has no sample to copy")

        # Check if target is occupied and overwrite is disabled
        if not overwrite and target_pad.is_assigned:
            raise ValueError(
                f"Target pad {target_index} already has sample '{target_pad.sample.name}'"
            )

        # Log if we're overwriting an existing sample
        if target_pad.is_assigned:
            logger.info(
                f"Overwriting pad {target_index} (was '{target_pad.sample.name}') "
                f"with duplicate from pad {source_index} ('{source_pad.sample.name}')"
            )
        else:
            logger.info(f"Duplicated sample '{source_pad.sample.name}' from pad {source_index} to pad {target_index}")

        # Deep copy entire source pad but preserve target position
        new_target = source_pad.model_copy(deep=True, update={'x': target_pad.x, 'y': target_pad.y})
        self.launchpad.pads[target_index] = new_target

        # Notify observers
        self._notify_observers(EditEvent.PAD_DUPLICATED, [target_index], [new_target])

        return new_target

    def copy_pad(self, pad_index: int) -> Pad:
        """
        Copy a pad to the clipboard buffer.

        Creates a deep copy of the pad and stores it in an internal buffer
        for later pasting.

        Args:
            pad_index: Index of pad to copy

        Returns:
            The copied Pad

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad is empty
        """
        self._validate_pad_index(pad_index)
        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned:
            raise ValueError(f"Cannot copy empty pad {pad_index}")

        # Deep copy the pad to clipboard
        self._clipboard = pad.model_copy(deep=True)

        logger.info(f"Copied pad {pad_index} ('{pad.sample.name}') to clipboard")
        return self._clipboard

    def paste_pad(self, target_index: int, overwrite: bool = False) -> Pad:
        """
        Paste the clipboard buffer to a target pad.

        Args:
            target_index: Index of pad to paste to
            overwrite: If False (default), raise ValueError if target already has a sample.
                      If True, replace target pad contents even if occupied.

        Returns:
            The new target Pad

        Raises:
            IndexError: If target_index is out of range
            ValueError: If clipboard is empty or target is occupied and overwrite=False
        """
        self._validate_pad_index(target_index, "Target pad index")

        if self._clipboard is None:
            raise ValueError("Clipboard is empty. Copy a pad first.")

        target_pad = self.launchpad.pads[target_index]

        # Check if target is occupied and overwrite is disabled
        if not overwrite and target_pad.is_assigned:
            raise ValueError(
                f"Target pad {target_index} already has sample '{target_pad.sample.name}'"
            )

        # Log if we're overwriting an existing sample
        if target_pad.is_assigned:
            logger.info(
                f"Overwriting pad {target_index} (was '{target_pad.sample.name}') "
                f"with paste from clipboard ('{self._clipboard.sample.name}')"
            )
        else:
            logger.info(f"Pasted sample '{self._clipboard.sample.name}' from clipboard to pad {target_index}")

        # Deep copy clipboard to target, preserving target position
        new_target = self._clipboard.model_copy(deep=True, update={'x': target_pad.x, 'y': target_pad.y})
        self.launchpad.pads[target_index] = new_target

        # Notify observers (treat paste as assignment to target)
        self._notify_observers(EditEvent.PAD_ASSIGNED, [target_index], [new_target])

        return new_target

    def cut_pad(self, pad_index: int) -> Pad:
        """
        Cut a pad to the clipboard buffer and clear the source.

        Atomically copies the pad to clipboard and clears the source pad.
        This is equivalent to copy_pad() followed by clear_pad().

        Args:
            pad_index: Index of pad to cut

        Returns:
            The copied Pad (now in clipboard)

        Raises:
            IndexError: If pad_index is out of range
            ValueError: If pad is empty
        """
        self._validate_pad_index(pad_index)
        pad = self.launchpad.pads[pad_index]

        if not pad.is_assigned:
            raise ValueError(f"Cannot cut empty pad {pad_index}")

        # Deep copy the pad to clipboard
        self._clipboard = pad.model_copy(deep=True)

        # Clear the source pad
        old_pad = self.launchpad.pads[pad_index]
        new_pad = Pad.empty(old_pad.x, old_pad.y)
        self.launchpad.pads[pad_index] = new_pad

        # Notify observers (source pad is now cleared)
        self._notify_observers(EditEvent.PAD_CLEARED, [pad_index], [new_pad])

        logger.info(f"Cut pad {pad_index} ('{self._clipboard.sample.name}') to clipboard")
        return self._clipboard

    def clear_all(self) -> int:
        """
        Clear all pads in the launchpad.

        Returns:
            Number of pads that were cleared (had samples)

        """
        cleared_count = 0
        for i in range(self.grid_size):
            pad = self.launchpad.pads[i]
            if pad.is_assigned:
                new_pad = Pad.empty(pad.x, pad.y)
                self.launchpad.pads[i] = new_pad
                cleared_count += 1

        logger.info(f"Cleared all pads ({cleared_count} pads had samples)")
        return cleared_count

    def clear_range(self, start_index: int, end_index: int) -> int:
        """
        Clear a range of pads.

        Args:
            start_index: First pad index (inclusive)
            end_index: Last pad index (inclusive)

        Returns:
            Number of pads that were cleared (had samples)

        Raises:
            IndexError: If start_index or end_index is out of range
            ValueError: If start_index > end_index
        """
        self._validate_pad_index(start_index, "Start pad index")
        self._validate_pad_index(end_index, "End pad index")

        if start_index > end_index:
            raise ValueError(f"Start index {start_index} must be <= end index {end_index}")

        cleared_count = 0
        for i in range(start_index, end_index + 1):
            pad = self.launchpad.pads[i]
            if pad.is_assigned:
                new_pad = Pad.empty(pad.x, pad.y)
                self.launchpad.pads[i] = new_pad
                cleared_count += 1

        logger.info(f"Cleared pads {start_index}-{end_index} ({cleared_count} pads had samples)")
        return cleared_count
