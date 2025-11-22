"""Color Management System - Device-Agnostic Color Definitions.

This module provides the single source of truth for all colors in the application.
Colors are defined as 8-bit RGB values (0-255) and converted as needed for different
hardware targets.

## Three Color Representations

The application uses three different color representations depending on context:

### 1. Standard 8-bit RGB (0-255)
**Purpose**: Internal representation throughout the application
**Format**: `Color(r=255, g=128, b=0)`
**Used by**: UI logic, configuration, state management

This is the primary color format. All colors in this module are defined using
standard 8-bit RGB values where each channel ranges from 0-255.

Example:
    ```python
    from launchsampler.colors import COLORS

    red = COLORS.RED          # Color(r=255, g=0, b=0)
    orange = COLORS.ORANGE    # Color(r=255, g=128, b=0)
    ```

### 2. MIDI 7-bit RGB (0-127)
**Purpose**: Hardware communication via MIDI SysEx messages
**Format**: `(127, 64, 0)` tuple
**Used by**: Device adapters when sending RGB LED commands

MIDI restricts values to 7 bits (0-127). Colors are converted using right bit shift:
`rgb_7bit = rgb_8bit >> 1`

Example:
    ```python
    color = Color(r=255, g=128, b=0)
    r7, g7, b7 = color.to_7bit()  # (127, 64, 0)
    ```

### 3. Hardware Palette Indices (0-127)
**Purpose**: Hardware animations (pulse, blink) that require firmware colors
**Format**: Integer index `42`
**Used by**: Device adapters for animation commands

Some hardware effects like pulsing require palette colors from the device's firmware.
These are approximated using Euclidean distance with LRU caching for performance.

Example:
    ```python
    from launchsampler.devices.launchpad import rgb_to_palette_index

    color = Color(r=255, g=0, b=0)
    palette_idx = rgb_to_palette_index(color)  # Find nearest palette color
    ```

## Color System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                           │
│  (UI logic, state management, configuration)                    │
│                                                                   │
│  Uses: 8-bit RGB Color objects from colors.COLORS               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Color objects passed down
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     Device Adapter Layer                        │
│  (Hardware-specific translation)                                │
│                                                                   │
│  • RGB mode:       color.to_7bit() → (127, 64, 0)              │
│  • Animation mode: rgb_to_palette_index(color) → 42            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Hardware-specific format
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     Hardware Layer                              │
│  (Launchpad, APC, etc.)                                         │
│                                                                   │
│  Receives: 7-bit RGB for static colors, palette index for      │
│            animations                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Basic Usage
```python
from launchsampler.colors import COLORS
from launchsampler.models import Color

# Use predefined colors
red = COLORS.RED
green = COLORS.GREEN
blue = COLORS.BLUE

# Or create custom colors
custom = Color(r=128, g=64, b=192)
```

### In UI Logic (Device-Agnostic)
```python
from launchsampler.colors import COLORS
from launchsampler.ui_shared.colors import MODE_COLORS, get_pad_color

# UI layer uses 8-bit colors directly
MODE_COLORS = {
    PlaybackMode.ONE_SHOT: COLORS.RED,
    PlaybackMode.LOOP: COLORS.GREEN,
}

# Get display color for a pad
color = get_pad_color(pad, is_playing=False)  # Returns Color object
```

### In Device Adapters (Hardware-Specific)
```python
from launchsampler.devices.launchpad import rgb_to_palette_index

def set_led_rgb(self, index: int, color: Color):
    '''Send RGB color to hardware (static mode).'''
    r7, g7, b7 = color.to_7bit()  # Convert to 7-bit
    self.send_sysex([0x03, index, r7, g7, b7])

def set_led_pulsing(self, index: int, color: Color):
    '''Send pulsing animation to hardware (requires palette).'''
    palette_idx = rgb_to_palette_index(color)  # Approximate to palette
    self.send_sysex([0x02, index, palette_idx])
```

## Color Conversion Details

### 8-bit → 7-bit Conversion (RGB Mode)
Fast bit shift operation, no loss of perceptual quality:
```python
r7 = r8 >> 1  # 255 >> 1 = 127
g7 = g8 >> 1  # 128 >> 1 = 64
b7 = b8 >> 1  # 0 >> 1 = 0
```

### 8-bit → Palette Index (Animation Mode)
Expensive Euclidean distance calculation with LRU cache:
```python
@lru_cache(maxsize=1024)
def rgb_to_palette_index(color: Color) -> int:
    '''Find nearest palette color using Euclidean distance.

    Cached for performance - typical hit rate >95% in real usage.
    '''
    min_distance = float('inf')
    best_index = 0

    for idx, palette_color in PALETTE.items():
        distance = sqrt((color.r - palette_color.r)**2 +
                       (color.g - palette_color.g)**2 +
                       (color.b - palette_color.b)**2)
        if distance < min_distance:
            min_distance = distance
            best_index = idx

    return best_index
```

## Performance Considerations

- **Color objects are frozen**: Hashable for use as dict keys and LRU cache
- **Palette approximation is cached**: LRU cache with 1024 slots
- **Expected cache hit rate**: >95% in real-world usage
- **Cache monitoring**: Use `get_cache_stats()` to monitor performance

## Design Principles

1. **Single Source of Truth**: All colors defined once in this module
2. **Device Agnostic**: UI layer has zero hardware knowledge
3. **Late Conversion**: Convert to hardware format only in device adapters
4. **Explicit Colors**: Named constants instead of magic RGB tuples
5. **Performance**: Caching expensive operations (palette approximation)

## Adding New Colors

To add a new color constant:

1. Add to the appropriate section below (PRIMARY, SECONDARY, etc.)
2. Use standard 8-bit RGB (0-255)
3. Name descriptively (avoid hardware-specific names like "PANIC_RED")

Example:
```python
# In colors/__init__.py COLORS class:
TURQUOISE = Color(r=64, g=224, b=208)
CORAL = Color(r=255, g=127, b=80)
```

## See Also

- `models.Color`: The Color Pydantic model with conversion methods
- `devices.launchpad.palette_mk3`: Launchpad MK3 palette definitions
- `ui_shared.colors`: UI color scheme (mode colors, playing colors, etc.)
"""

from launchsampler.models import Color


class COLORS:
    """Standard color constants - 8-bit RGB (0-255).

    These colors are device-agnostic and represent the application's
    color palette. Device adapters convert these to hardware-specific formats.

    All colors use standard 8-bit RGB values (0-255 per channel).
    """

    # ============================================================================
    # PRIMARY COLORS (Full saturation)
    # ============================================================================

    RED: Color = Color(r=255, g=0, b=0)
    """Pure red - Used for ONE_SHOT mode"""

    GREEN: Color = Color(r=0, g=255, b=0)
    """Pure green - Used for LOOP mode"""

    BLUE: Color = Color(r=0, g=0, b=255)
    """Pure blue - Used for HOLD mode"""

    YELLOW: Color = Color(r=255, g=255, b=0)
    """Pure yellow - Used for playing state"""

    MAGENTA: Color = Color(r=255, g=0, b=255)
    """Pure magenta - Used for LOOP_TOGGLE mode"""

    CYAN: Color = Color(r=0, g=255, b=255)
    """Pure cyan"""

    WHITE: Color = Color(r=255, g=255, b=255)
    """Pure white - Maximum brightness"""

    BLACK: Color = Color(r=0, g=0, b=0)
    """Black (off) - Used for empty pads"""

    # ============================================================================
    # SECONDARY COLORS
    # ============================================================================

    ORANGE: Color = Color(r=255, g=128, b=0)
    """Orange - Used for TOGGLE mode"""

    PURPLE: Color = Color(r=128, g=0, b=255)
    """Purple"""

    PINK: Color = Color(r=255, g=0, b=128)
    """Pink"""

    LIME: Color = Color(r=128, g=255, b=0)
    """Lime green"""

    TEAL: Color = Color(r=0, g=255, b=128)
    """Teal"""

    INDIGO: Color = Color(r=0, g=128, b=255)
    """Indigo"""

    # ============================================================================
    # GREYS
    # ============================================================================

    GREY_DARKEST: Color = Color(r=32, g=32, b=32)
    """Darkest grey - 12.5% brightness"""

    GREY_DARK: Color = Color(r=64, g=64, b=64)
    """Dark grey - 25% brightness"""

    GREY: Color = Color(r=128, g=128, b=128)
    """Mid grey - 50% brightness"""

    GREY_LIGHT: Color = Color(r=192, g=192, b=192)
    """Light grey - 75% brightness"""

    GREY_LIGHTEST: Color = Color(r=224, g=224, b=224)
    """Lightest grey - 88% brightness"""

    # ============================================================================
    # SHADES & VARIANTS
    # ============================================================================

    RED_DARK: Color = Color(r=90, g=0, b=0)
    """Dark red - Used for panic button indicator"""


__all__ = ["COLORS"]
