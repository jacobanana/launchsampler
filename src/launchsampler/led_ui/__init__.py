"""LED UI for Launchpad hardware.

=== "Architecture Overview"
    ```
    ┌─────────────────────────────────────────────────────┐
    │  Application Layer (TUI/Core)                       │
    │  - Pad state changes, UI updates                    │
    │  - Works with logical pad indices (0-63)            │
    │  - Works with (x, y) coordinates (0-7, 0-7)         │
    └────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────▼────────────────────────────────────┐
    │  Generic Device Abstraction                         │
    │  - Device: input + output layers                    │
    │  - DeviceInput: parse messages → events             │
    │  - DeviceOutput: state → hardware messages          │
    └────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────▼────────────────────────────────────┐
    │  Launchpad Device (Concrete Implementation)         │
    │  ├─ LaunchpadModel (detection & metadata)           │
    │  ├─ LaunchpadInput (parse MIDI → pad events)        │
    │  │  └─ NoteMapper (note → index/coordinates)        │
    │  └─ LaunchpadOutput (LED display control)           │
    │     └─ IndexMapper (index/coordinates → note)       │
    └────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────▼────────────────────────────────────┐
    │  Launchpad Protocol Layer                           │
    │  ├─ SysEx message builder                           │
    │  ├─ Color palette                                   │
    │  └─ Lighting modes                                  │
    └────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────▼────────────────────────────────────┐
    │  MIDI Transport (Existing)                          │
    │  - MidiManager (send/receive)                       │
    └─────────────────────────────────────────────────────┘
    ```

"""

from .app import LaunchpadLEDUI

__all__ = ["LaunchpadLEDUI"]
