"""
Generic MIDI input parsing for all devices.

Input Flow: Button Press → Your Code
=====================================

This module handles the INPUT SIDE of device communication - transforming
hardware MIDI messages into logical application events.

The Flow
--------

::

    Hardware Button Press
          ↓
    [MIDI Message: note_on 36, velocity 100]
          ↓
    ┌──────────────────────────────────────┐
    │      GenericInput                    │
    │       (input.py)                     │
    │                                      │
    │  parse_message(msg):                 │
    │    if msg.type == 'note_on':         │
    │      index = mapper.note_to_index(36)│
    │      return PadPressEvent(index=5)   │
    └────────────┬─────────────────────────┘
                 │ Uses mapper
                 ↓
    ┌──────────────────────────────────────┐
    │   LaunchpadMK3Mapper                 │
    │   (adapters/launchpad_mk3.py)        │
    │                                      │
    │  note_to_index(36):                  │
    │    offset = 11                       │
    │    row_spacing = 10                  │
    │    note_index = note - offset = 25   │
    │    row = 25 // 10 = 2                │
    │    col = 25 % 10 = 5                 │
    │    return row * 8 + col = 21         │
    │                                      │
    │  Hardware layout:                    │
    │    Note 11 = bottom-left (0,0)       │
    │    Note 36 = pad at (2,5)            │
    │    Logical index 21                  │
    └──────────────────────────────────────┘
          ↓
    [PadPressEvent(pad_index=21, velocity=100)]
          ↓
    Your application observers get notified

Key Concepts
------------

**Hardware Independence**: GenericInput knows nothing about specific devices.
It just asks the mapper "what logical index is this MIDI note?"

**Logical vs Hardware Indices**:
- Hardware: MIDI note 36 (device-specific)
- Logical: Pad index 21 (universal across all devices)

**Velocity Handling**: MIDI velocity (0-127) is preserved for pressure-sensitive
applications. Note that velocity=0 on note_on is actually a note_off.
"""

from typing import Protocol

import mido

from .protocols import ControlChangeEvent, DeviceEvent, DeviceInput, PadPressEvent, PadReleaseEvent


class NoteMapper(Protocol):
    """Protocol for device-specific note mapping."""

    def note_to_index(self, note: int) -> int | None:
        """Convert hardware MIDI note to logical pad index."""
        ...

    def index_to_note(self, index: int) -> int:
        """Convert logical pad index to hardware MIDI note."""
        ...


class GenericInput(DeviceInput):
    """
    Generic MIDI input parser.

    Handles standard MIDI messages (note_on, note_off, control_change)
    and delegates hardware-specific note mapping to a device mapper.
    """

    mapper: NoteMapper

    def __init__(self, mapper: NoteMapper):
        """
        Initialize generic input parser.

        Args:
            mapper: Device-specific note mapper for converting
                   hardware MIDI notes to logical pad indices
        """
        self.mapper = mapper

    def parse_message(self, msg: mido.Message) -> DeviceEvent | None:
        """
        Parse incoming MIDI message into device events.

        Transforms hardware MIDI note numbers to logical pad indices
        using the device-specific note mapper.

        Args:
            msg: MIDI message

        Returns:
            DeviceEvent with logical pad index, or None if message
            should be ignored or is not supported
        """
        # Filter out clock messages
        if msg.type == "clock":
            return None

        # Handle note on/off
        if msg.type == "note_on":
            # Convert note to logical index using device mapper
            pad_index = self.mapper.note_to_index(msg.note)
            if pad_index is None:
                return None  # Invalid note, not a grid pad

            # Note on with velocity 0 is actually note off
            if msg.velocity > 0:
                return PadPressEvent(pad_index, msg.velocity)
            else:
                return PadReleaseEvent(pad_index)

        elif msg.type == "note_off":
            pad_index = self.mapper.note_to_index(msg.note)
            if pad_index is None:
                return None
            return PadReleaseEvent(pad_index)

        elif msg.type == "control_change":
            return ControlChangeEvent(msg.control, msg.value)

        return None
