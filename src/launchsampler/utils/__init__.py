"""Generic utility modules for launchsampler.

This package contains generic utilities that are not specific to any domain:
- paths: Path manipulation and common path finding
- audio: Audio processing utilities (numpy array handling)
- File size formatting
"""

from .audio import ensure_array
from .paths import find_common_path, format_bytes

__all__ = ["ensure_array", "find_common_path", "format_bytes"]
