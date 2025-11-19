"""Enumerations for the Launchpad sampler."""

from enum import Enum
from .color import Color


class LaunchpadColor(Enum):
    """Complete Launchpad palette (128 colors) with both RGB and palette index.

    Each color is a tuple of (Color, palette_index).
    Based on Launchpad MK2/Pro palette.
    """

    # Greys/Whites (0-3)
    BLACK = (Color(r=0, g=0, b=0), 0)
    DARK_GREY = (Color(r=14, g=14, b=14), 1)
    GREY = (Color(r=62, g=62, b=62), 2)
    WHITE = (Color(r=126, g=126, b=126), 3)

    # Reds (4-7)
    RED_BRIGHT = (Color(r=127, g=39, b=36), 4)
    RED = (Color(r=127, g=5, b=0), 5)
    RED_DARK = (Color(r=45, g=0, b=0), 6)
    RED_DARKER = (Color(r=12, g=0, b=1), 7)
    PANIC_RED = (Color(r=45, g=0, b=0), 6)  # Dark red for panic/emergency stop

    # Oranges (8-11)
    ORANGE_BRIGHT = (Color(r=127, g=94, b=49), 8)
    ORANGE = (Color(r=127, g=43, b=0), 9)
    ORANGE_DARK = (Color(r=45, g=14, b=0), 10)
    ORANGE_DARKER = (Color(r=18, g=12, b=1), 11)

    # Yellows (12-15)
    YELLOW_BRIGHT = (Color(r=126, g=126, b=16), 12)
    YELLOW = (Color(r=126, g=126, b=0), 13)
    YELLOW_DARK = (Color(r=44, g=44, b=0), 14)
    YELLOW_DARKER = (Color(r=12, g=12, b=0), 15)

    # Lime/Yellow-Green (16-19)
    LIME_BRIGHT = (Color(r=64, g=126, b=21), 16)
    LIME = (Color(r=32, g=126, b=0), 17)
    LIME_DARK = (Color(r=11, g=44, b=0), 18)
    LIME_DARKER = (Color(r=9, g=20, b=0), 19)

    # Green (20-23)
    GREEN_BRIGHT = (Color(r=26, g=126, b=21), 20)
    GREEN = (Color(r=0, g=127, b=0), 21)
    GREEN_DARK = (Color(r=0, g=44, b=0), 22)
    GREEN_DARKER = (Color(r=0, g=12, b=0), 23)

    # Spring Green (24-27)
    SPRING_GREEN_BRIGHT = (Color(r=26, g=126, b=35), 24)
    SPRING_GREEN = (Color(r=0, g=127, b=0), 25)
    SPRING_GREEN_DARK = (Color(r=0, g=44, b=0), 26)
    SPRING_GREEN_DARKER = (Color(r=0, g=12, b=0), 27)

    # Turquoise/Cyan (28-31)
    TURQUOISE_BRIGHT = (Color(r=25, g=126, b=63), 28)
    TURQUOISE = (Color(r=0, g=126, b=29), 29)
    TURQUOISE_DARK = (Color(r=0, g=44, b=10), 30)
    TURQUOISE_DARKER = (Color(r=0, g=14, b=7), 31)

    # Cyan (32-35)
    CYAN_BRIGHT = (Color(r=23, g=126, b=88), 32)
    CYAN = (Color(r=0, g=125, b=72), 33)
    CYAN_DARK = (Color(r=0, g=43, b=25), 34)
    CYAN_DARKER = (Color(r=0, g=12, b=8), 35)

    # Sky Blue (36-39)
    SKY_BLUE_BRIGHT = (Color(r=28, g=95, b=127), 36)
    SKY_BLUE = (Color(r=0, g=83, b=127), 37)
    SKY_BLUE_DARK = (Color(r=0, g=32, b=40), 38)
    SKY_BLUE_DARKER = (Color(r=0, g=8, b=12), 39)

    # Ocean Blue (40-43)
    OCEAN_BLUE_BRIGHT = (Color(r=32, g=67, b=127), 40)
    OCEAN_BLUE = (Color(r=0, g=40, b=127), 41)
    OCEAN_BLUE_DARK = (Color(r=0, g=13, b=45), 42)
    OCEAN_BLUE_DARKER = (Color(r=0, g=3, b=12), 43)

    # Blue (44-47)
    BLUE_BRIGHT = (Color(r=35, g=35, b=127), 44)
    BLUE = (Color(r=0, g=0, b=127), 45)
    BLUE_DARK = (Color(r=0, g=0, b=45), 46)
    BLUE_DARKER = (Color(r=0, g=0, b=12), 47)

    # Purple (48-51)
    PURPLE_BRIGHT = (Color(r=65, g=35, b=127), 48)
    PURPLE = (Color(r=40, g=0, b=127), 49)
    PURPLE_DARK = (Color(r=11, g=0, b=51), 50)
    PURPLE_DARKER = (Color(r=5, g=0, b=25), 51)

    # Magenta (52-55)
    MAGENTA_BRIGHT = (Color(r=127, g=36, b=127), 52)
    MAGENTA = (Color(r=127, g=0, b=127), 53)
    MAGENTA_DARK = (Color(r=45, g=0, b=45), 54)
    MAGENTA_DARKER = (Color(r=12, g=0, b=12), 55)

    # Pink (56-59)
    PINK_BRIGHT = (Color(r=125, g=39, b=65), 56)
    PINK = (Color(r=127, g=3, b=41), 57)
    PINK_DARK = (Color(r=45, g=1, b=13), 58)
    PINK_DARKER = (Color(r=16, g=0, b=8), 59)

    # Additional colors (60-127)
    COLOR_60 = (Color(r=127, g=12, b=0), 60)
    COLOR_61 = (Color(r=77, g=26, b=0), 61)
    COLOR_62 = (Color(r=61, g=40, b=0), 62)
    COLOR_63 = (Color(r=31, g=50, b=0), 63)
    COLOR_64 = (Color(r=0, g=28, b=0), 64)
    COLOR_65 = (Color(r=0, g=42, b=25), 65)
    COLOR_66 = (Color(r=0, g=41, b=63), 66)
    BLUE_PURE = (Color(r=0, g=0, b=127), 67)
    COLOR_68 = (Color(r=0, g=34, b=38), 68)
    COLOR_69 = (Color(r=13, g=0, b=104), 69)
    GREY_MID = (Color(r=62, g=62, b=62), 70)
    GREY_DARK = (Color(r=16, g=16, b=16), 71)
    RED_PURE = (Color(r=127, g=5, b=0), 72)
    LIME_YELLOW = (Color(r=93, g=126, b=0), 73)
    LIME_GREEN = (Color(r=86, g=118, b=0), 74)
    GREEN_LIME = (Color(r=43, g=126, b=0), 75)
    GREEN_PURE = (Color(r=0, g=68, b=0), 76)
    CYAN_GREEN = (Color(r=0, g=126, b=61), 77)
    SKY = (Color(r=0, g=83, b=127), 78)
    BLUE_OCEAN = (Color(r=1, g=13, b=127), 79)
    VIOLET = (Color(r=26, g=0, b=127), 80)
    PURPLE_BLUE = (Color(r=60, g=0, b=127), 81)
    PINK_PURPLE = (Color(r=90, g=11, b=63), 82)
    BROWN_DARK = (Color(r=32, g=16, b=0), 83)
    ORANGE_RED = (Color(r=127, g=37, b=0), 84)
    GREEN_YELLOW = (Color(r=65, g=112, b=0), 85)
    LIME_BRIGHT_ALT = (Color(r=51, g=126, b=0), 86)
    GREEN_BRIGHT_ALT = (Color(r=0, g=127, b=0), 87)
    GREEN_ALT = (Color(r=0, g=127, b=0), 88)
    MINT = (Color(r=34, g=126, b=48), 89)
    CYAN_BRIGHT_ALT = (Color(r=0, g=125, b=101), 90)
    BLUE_SKY = (Color(r=40, g=67, b=127), 91)
    BLUE_MEDIUM = (Color(r=19, g=38, b=100), 92)
    LAVENDER = (Color(r=66, g=61, b=118), 93)
    MAGENTA_PURPLE = (Color(r=105, g=6, b=127), 94)
    ROSE = (Color(r=127, g=3, b=45), 95)
    ORANGE_BRIGHT_ALT = (Color(r=127, g=62, b=0), 96)
    YELLOW_GREEN = (Color(r=92, g=88, b=0), 97)
    CHARTREUSE = (Color(r=69, g=126, b=0), 98)
    BROWN = (Color(r=64, g=46, b=0), 99)
    BROWN_DARKER = (Color(r=29, g=20, b=1), 100)
    FOREST_GREEN_DARK = (Color(r=6, g=38, b=2), 101)
    TEAL_DARK = (Color(r=0, g=40, b=27), 102)
    NAVY = (Color(r=9, g=10, b=20), 103)
    BLUE_NAVY = (Color(r=8, g=15, b=45), 104)
    BROWN_MID = (Color(r=53, g=30, b=12), 105)
    RED_CRIMSON = (Color(r=86, g=2, b=0), 106)
    CORAL = (Color(r=112, g=40, b=27), 107)
    AMBER = (Color(r=110, g=52, b=0), 108)
    GOLD = (Color(r=127, g=112, b=0), 109)
    YELLOW_LIME = (Color(r=76, g=112, b=0), 110)
    OLIVE = (Color(r=48, g=90, b=0), 111)
    DARK_BLUE = (Color(r=13, g=14, b=24), 112)
    LIME_PASTEL = (Color(r=110, g=126, b=42), 113)
    MINT_PASTEL = (Color(r=59, g=125, b=92), 114)
    PERIWINKLE = (Color(r=75, g=76, b=127), 115)
    PURPLE_PASTEL = (Color(r=69, g=49, b=127), 116)
    GREY_40 = (Color(r=32, g=32, b=32), 117)
    GREY_74 = (Color(r=58, g=58, b=58), 118)
    CYAN_PALE = (Color(r=111, g=126, b=126), 119)
    RED_MAROON = (Color(r=81, g=2, b=0), 120)
    MAROON_DARK = (Color(r=26, g=0, b=0), 121)
    GREEN_EMERALD = (Color(r=0, g=105, b=0), 122)
    GREEN_FOREST = (Color(r=0, g=32, b=0), 123)
    KHAKI = (Color(r=92, g=88, b=0), 124)
    OLIVE_DARK = (Color(r=30, g=24, b=0), 125)
    RUST = (Color(r=90, g=46, b=0), 126)
    RUST_DARK = (Color(r=38, g=9, b=0), 127)

    @property
    def rgb(self) -> Color:
        """Get the RGB Color value."""
        return self.value[0]

    @property
    def palette(self) -> int:
        """Get the palette index (0-127)."""
        return self.value[1]


class PlaybackMode(str, Enum):
    """Audio playback modes."""

    ONE_SHOT = "one_shot"          # Play from start on each note_on, plays to end
    TOGGLE = "toggle"              # Toggle playback on/off with note_on
    HOLD = "hold"                  # Play once while note held, stop on note_off
    LOOP = "loop"                  # Loop continuously, restart on note_on
    LOOP_TOGGLE = "loop_toggle"    # Toggle looping on/off with note_on
