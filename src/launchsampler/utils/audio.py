"""Audio processing utilities."""

import numpy as np
import numpy.typing as npt


def ensure_array(value: np.float32 | npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    """
    Ensure numpy operation result is an array.

    Some numpy operations like np.mean() can return either a scalar or an array
    depending on the input shape and parameters. This utility ensures the result
    is always an array for consistent type handling.

    Args:
        value: Result from a numpy operation that may be scalar or array

    Returns:
        Always returns an ndarray[float32]

    Example:
        >>> result = np.mean(data, axis=1, dtype=np.float32)
        >>> array_result = ensure_array(result)
    """
    return value if isinstance(value, np.ndarray) else np.array([value], dtype=np.float32)
