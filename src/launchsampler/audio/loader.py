"""Sample loader for loading audio files."""

from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from .data import AudioData


class SampleLoader:
    """
    Load audio files into AudioData structures.

    Handles WAV, FLAC, OGG, and other formats supported by soundfile.
    """

    def __init__(self, target_sample_rate: Optional[int] = None):
        """
        Initialize sample loader.

        Args:
            target_sample_rate: If set, resample all audio to this rate.
                               If None, use original sample rate.
        """
        self.target_sample_rate = target_sample_rate

    def load(self, path: Path) -> AudioData:
        """
        Load audio file.

        Args:
            path: Path to audio file

        Returns:
            AudioData containing the loaded audio

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If file cannot be loaded
        """
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        try:
            # Load audio file
            data, sample_rate = sf.read(str(path), dtype='float32')

            # Handle empty files
            if len(data) == 0:
                raise RuntimeError(f"Audio file is empty: {path}")

            # Resample if needed
            if self.target_sample_rate and sample_rate != self.target_sample_rate:
                data = self._resample(data, sample_rate, self.target_sample_rate)
                sample_rate = self.target_sample_rate

            # Create AudioData
            return AudioData.from_array(data, sample_rate)

        except Exception as e:
            raise RuntimeError(f"Failed to load audio file {path}: {e}") from e

    def _resample(
        self,
        data: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """
        Simple linear resampling.

        For production, you might want to use a library like resampy or librosa
        for higher quality resampling.

        Args:
            data: Audio data
            orig_sr: Original sample rate
            target_sr: Target sample rate

        Returns:
            Resampled audio data
        """
        if orig_sr == target_sr:
            return data

        # Calculate new length
        ratio = target_sr / orig_sr
        new_length = int(len(data) * ratio)

        # Linear interpolation
        if data.ndim == 1:
            # Mono
            x_old = np.linspace(0, 1, len(data))
            x_new = np.linspace(0, 1, new_length)
            resampled = np.interp(x_new, x_old, data).astype(np.float32)
        else:
            # Multi-channel
            x_old = np.linspace(0, 1, len(data))
            x_new = np.linspace(0, 1, new_length)
            resampled = np.zeros((new_length, data.shape[1]), dtype=np.float32)
            for ch in range(data.shape[1]):
                resampled[:, ch] = np.interp(x_new, x_old, data[:, ch])

        return resampled

    @staticmethod
    def get_info(path: Path) -> dict:
        """
        Get audio file info without loading the full file.

        Args:
            path: Path to audio file

        Returns:
            Dictionary with 'sample_rate', 'channels', 'frames', 'duration'

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        info = sf.info(str(path))
        return {
            'sample_rate': info.samplerate,
            'channels': info.channels,
            'frames': info.frames,
            'duration': info.duration,
            'format': info.format,
            'subtype': info.subtype,
        }
