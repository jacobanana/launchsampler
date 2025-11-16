"""Note mapping for Launchpad devices."""

from typing import Tuple, Optional
from .model import LaunchpadModel


class LaunchpadNoteMapper:
    """
    Bidirectional mapping between MIDI notes and pad indices/coordinates.

    Different Launchpad models may use different note layouts:
    - Some models: Note 0 = bottom-left pad
    - Some models: Note 11 = bottom-left pad (Programmer mode)

    This class abstracts these differences and provides:
    - note_to_index(): MIDI note → logical index (0-63)
    - note_to_xy(): MIDI note → (x, y) coordinates
    - index_to_note(): logical index → MIDI note
    - xy_to_note(): (x, y) coordinates → MIDI note
    """

    # Programmer mode layout (most common for LED control)
    # Bottom-left = note 11, bottom-right = note 18
    # Top-left = note 81, top-right = note 88
    # Row spacing = 10 (includes non-existent notes 19, 29, etc.)
    PROGRAMMER_MODE_OFFSET = 11
    PROGRAMMER_MODE_ROW_SPACING = 10

    def __init__(self, model: LaunchpadModel, mode: str = "programmer"):
        """
        Initialize note mapper for specific model and mode.

        Args:
            model: LaunchpadModel enum
            mode: "programmer" or "live" (default: programmer)
        """
        self.model = model
        self.mode = mode

        # For now, all models use same mapping in programmer mode
        # Future: model-specific layouts if needed
        self.offset = self.PROGRAMMER_MODE_OFFSET
        self.row_spacing = self.PROGRAMMER_MODE_ROW_SPACING

    def note_to_index(self, note: int) -> Optional[int]:
        """
        Convert MIDI note to logical pad index (0-63).

        Args:
            note: MIDI note number

        Returns:
            Pad index (0-63) or None if invalid note

        Example:
            note 11 → index 0 (bottom-left)
            note 18 → index 7 (bottom-right)
            note 81 → index 56 (top-left)
            note 88 → index 63 (top-right)
        """
        # Calculate row and column from note
        x, y = self.note_to_xy(note)
        if x is None or y is None:
            return None

        # Convert to linear index
        return y * 8 + x

    def note_to_xy(self, note: int) -> Tuple[Optional[int], Optional[int]]:
        """
        Convert MIDI note to (x, y) coordinates.

        Args:
            note: MIDI note number

        Returns:
            (x, y) tuple or (None, None) if invalid
            x: column (0-7, left to right)
            y: row (0-7, bottom to top)
        """
        # Validate note range (11-88 in programmer mode)
        if note < self.offset or note > (self.offset + 7 * self.row_spacing + 7):
            return (None, None)

        # Remove offset
        adjusted = note - self.offset

        # Calculate row and column
        row = adjusted // self.row_spacing
        col = adjusted % self.row_spacing

        # Validate column (must be 0-7)
        if col > 7:
            return (None, None)

        # Validate row (must be 0-7)
        if row > 7:
            return (None, None)

        return (col, row)  # x=col, y=row

    def index_to_note(self, index: int) -> Optional[int]:
        """
        Convert logical pad index to MIDI note.

        Args:
            index: Pad index (0-63)

        Returns:
            MIDI note number or None if invalid index
        """
        if not 0 <= index < 64:
            return None

        # Convert to x, y
        row = index // 8
        col = index % 8

        return self.xy_to_note(col, row)

    def xy_to_note(self, x: int, y: int) -> Optional[int]:
        """
        Convert (x, y) coordinates to MIDI note.

        Args:
            x: column (0-7)
            y: row (0-7, bottom to top)

        Returns:
            MIDI note number or None if invalid coordinates
        """
        if not (0 <= x < 8 and 0 <= y < 8):
            return None

        # Note = offset + (row * row_spacing) + col
        return self.offset + (y * self.row_spacing) + x
