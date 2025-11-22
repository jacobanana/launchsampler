"""Launchpad palette utilities and conversions."""

from functools import lru_cache

from launchsampler.models import Color

from .colors import LaunchpadColor

# Precompute lookup dictionaries for O(1) access
# Built once at module load time
_PALETTE_TO_COLOR: dict[int, Color] = {
    palette_color.palette: palette_color.rgb for palette_color in LaunchpadColor
}

_ALL_PALETTE_COLORS: list[tuple[int, Color]] = [
    (palette_color.palette, palette_color.rgb) for palette_color in LaunchpadColor
]


class LaunchpadPalette:
    """
    Launchpad palette utilities.

    Provides conversion between RGB colors and the Launchpad's 128-color palette.
    Uses the LaunchpadColor enum for palette definitions.

    Performance:
    - Precomputed lookup dictionaries for O(1) palette index → color
    - from_color() uses LRU cache to avoid repeated distance calculations
    - Cache size of 128 covers common color palette usage
    """

    @staticmethod
    @lru_cache(maxsize=128)
    def from_color(color: Color) -> int:
        """
        Convert RGB color to nearest Launchpad palette index.

        Uses Euclidean distance in RGB space to find the closest match
        in the Launchpad's 128-color palette.

        Args:
            color: RGB color object (0-127 per channel)

        Returns:
            Palette color index (0-127)

        Example:
            >>> color = Color(r=127, g=0, b=0)
            >>> palette_index = LaunchpadPalette.from_color(color)
            >>> palette_index
            5  # RED palette index
        """
        min_distance = float("inf")
        closest_palette_index = 0

        # Find closest palette color using Euclidean distance
        # Use precomputed list for faster iteration
        for palette_index, palette_rgb in _ALL_PALETTE_COLORS:
            # Calculate Euclidean distance in RGB space
            distance = (
                (color.r - palette_rgb.r) ** 2
                + (color.g - palette_rgb.g) ** 2
                + (color.b - palette_rgb.b) ** 2
            ) ** 0.5

            if distance < min_distance:
                min_distance = distance
                closest_palette_index = palette_index

        return closest_palette_index

    @staticmethod
    def to_color(palette_index: int) -> Color:
        """
        Get RGB color for a Launchpad palette index.

        Args:
            palette_index: Palette index (0-127)

        Returns:
            RGB color object

        Raises:
            ValueError: If palette_index is not in range 0-127

        Example:
            >>> color = LaunchpadPalette.to_color(5)  # RED
            >>> color
            Color(r=127, g=5, b=0)
        """
        if not 0 <= palette_index <= 127:
            raise ValueError(f"Palette index must be 0-127, got {palette_index}")

        # O(1) dictionary lookup using precomputed table
        color = _PALETTE_TO_COLOR.get(palette_index)
        if color is None:
            raise ValueError(f"No color found for palette index {palette_index}")

        return color
