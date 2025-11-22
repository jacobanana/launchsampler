"""Color definitions for the application.

This module provides a centralized color palette for the entire application.
All colors are defined as device-agnostic 8-bit RGB values (0-255).

The color system supports three different representations:
1. **8-bit RGB (0-255)**: Standard representation used throughout the app
2. **7-bit RGB (0-127)**: For MIDI SysEx messages (converted via bit shift)
3. **Palette indices (0-127)**: For hardware animations (converted via approximation)

Device adapters handle conversion between these representations as needed.

Usage:
    from launchsampler.colors import COLORS

    # Use predefined colors
    red = COLORS.RED
    green = COLORS.GREEN

    # Or create custom colors
    custom = Color(r=128, g=64, b=192)

    # Convert for different contexts
    hex_color = custom.to_hex()          # For CSS
    r7, g7, b7 = custom.to_7bit()       # For MIDI
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

    RED = Color(r=255, g=0, b=0)
    GREEN = Color(r=0, g=255, b=0)
    BLUE = Color(r=0, g=0, b=255)
    YELLOW = Color(r=255, g=255, b=0)
    MAGENTA = Color(r=255, g=0, b=255)
    CYAN = Color(r=0, g=255, b=255)
    WHITE = Color(r=255, g=255, b=255)
    BLACK = Color(r=0, g=0, b=0)

    # ============================================================================
    # SECONDARY COLORS
    # ============================================================================

    ORANGE = Color(r=255, g=128, b=0)
    PURPLE = Color(r=128, g=0, b=255)
    PINK = Color(r=255, g=0, b=128)
    LIME = Color(r=128, g=255, b=0)
    TEAL = Color(r=0, g=255, b=128)
    INDIGO = Color(r=0, g=128, b=255)

    # ============================================================================
    # GREYS
    # ============================================================================

    GREY_DARKEST = Color(r=32, g=32, b=32)
    GREY_DARK = Color(r=64, g=64, b=64)
    GREY = Color(r=128, g=128, b=128)
    GREY_LIGHT = Color(r=192, g=192, b=192)
    GREY_LIGHTEST = Color(r=224, g=224, b=224)

    # ============================================================================
    # SHADES & VARIANTS
    # ============================================================================

    # Dark red
    RED_DARK = Color(r=90, g=0, b=0)


__all__ = ["COLORS"]
