"""Audio data structures using dataclasses for performance.

These dataclasses store actual audio data (NumPy arrays) and runtime state.
They are NOT Pydantic models because:
- They contain non-serializable data (NumPy arrays)
- They need minimal overhead for real-time audio processing
- They are internal to the audio engine, not part of the API
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import numpy.typing as npt

from ..models import PlaybackMode


@dataclass
class AudioData:
    """
    Raw audio data storage.

    This is kept separate from Pydantic models for performance.
    Contains the actual audio buffer that will be played back.
    """

    data: npt.NDArray[np.float32]  # Audio samples as float32
    sample_rate: int                # Sample rate in Hz
    num_channels: int               # Number of channels (1=mono, 2=stereo)
    num_frames: int                 # Number of frames (samples per channel)

    @classmethod
    def from_array(
        cls,
        data: npt.NDArray[np.float32],
        sample_rate: int
    ) -> "AudioData":
        """
        Create AudioData from a NumPy array.

        Args:
            data: Audio data as float32 array
                  Shape: (num_frames,) for mono or (num_frames, num_channels) for multi-channel
            sample_rate: Sample rate in Hz

        Returns:
            AudioData instance
        """
        if data.ndim == 1:
            # Mono audio
            num_channels = 1
            num_frames = len(data)
        elif data.ndim == 2:
            # Multi-channel audio
            num_frames, num_channels = data.shape
        else:
            raise ValueError(f"Audio data must be 1D or 2D, got {data.ndim}D")

        # Ensure float32 dtype
        if data.dtype != np.float32:
            data = data.astype(np.float32)

        return cls(
            data=data,
            sample_rate=sample_rate,
            num_channels=num_channels,
            num_frames=num_frames
        )

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.num_frames / self.sample_rate

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape of audio data array."""
        return self.data.shape

    def get_mono(self) -> npt.NDArray[np.float32]:
        """
        Get mono version of audio data.

        If already mono, returns original data.
        If stereo/multi-channel, returns average of all channels.
        """
        if self.num_channels == 1:
            return self.data
        else:
            return np.mean(self.data, axis=1, dtype=np.float32)

    def normalize(self, target_level: float = 0.95) -> None:
        """
        Normalize audio data to target level.

        Args:
            target_level: Target peak level (0.0 to 1.0)
        """
        peak = np.abs(self.data).max()
        if peak > 0:
            self.data *= (target_level / peak)


@dataclass
class PlaybackState:
    """
    Runtime playback state for a single pad.

    This is NOT a Pydantic model because it's purely internal state
    that changes rapidly during audio playback and should have minimal overhead.
    """

    is_playing: bool = False                    # Currently playing
    position: float = 0.0                       # Current playback position (in frames)
    mode: PlaybackMode = PlaybackMode.ONE_SHOT  # Playback mode
    volume: float = 1.0                         # Playback volume (0.0-1.0)
    audio_data: Optional[AudioData] = None      # Reference to audio data

    # Internal state
    _loop_count: int = field(default=0, init=False)        # Number of loops completed

    def start(self) -> None:
        """Start playback from the beginning."""
        if self.audio_data is None:
            raise ValueError("Cannot start playback without audio data")

        self.is_playing = True
        self.position = 0.0
        self._loop_count = 0

    def stop(self) -> None:
        """Stop playback."""
        self.is_playing = False

    def reset(self) -> None:
        """Reset to initial state."""
        self.is_playing = False
        self.position = 0.0
        self._loop_count = 0

    def advance(self, num_frames: int) -> None:
        """
        Advance playback position by num_frames.

        Handles looping and stopping based on playback mode.

        Args:
            num_frames: Number of frames to advance
        """
        if not self.is_playing or self.audio_data is None:
            return

        self.position += num_frames

        # Check if we've reached the end
        if self.position >= self.audio_data.num_frames:
            if self.mode == PlaybackMode.LOOP:
                # Loop back to start
                self.position = self.position % self.audio_data.num_frames
                self._loop_count += 1
            else:
                # ONE_SHOT or HOLD - stop at end
                self.stop()

    def get_frames(self, num_frames: int) -> Optional[npt.NDArray[np.float32]]:
        """
        Get next audio frames for playback.

        Handles seamless looping when in LOOP mode by wrapping around
        the end of the buffer.

        Args:
            num_frames: Number of frames to get

        Returns:
            Audio frames as float32 array, or None if not playing
        """
        if not self.is_playing or self.audio_data is None:
            return None

        start_pos = int(self.position)
        total_frames = self.audio_data.num_frames

        # Handle end of buffer for non-loop modes
        if start_pos >= total_frames:
            return None

        end_pos = start_pos + num_frames

        # Check if we need to wrap around (for LOOP mode)
        if end_pos > total_frames:
            if self.mode == PlaybackMode.LOOP:
                # Seamlessly wrap around for looping
                # Get frames from current position to end
                if self.audio_data.num_channels == 1:
                    first_part = self.audio_data.data[start_pos:total_frames]
                else:
                    first_part = self.audio_data.data[start_pos:total_frames, :]

                # Calculate how many frames we need from the beginning
                remaining_frames = num_frames - (total_frames - start_pos)

                # Get frames from beginning
                if self.audio_data.num_channels == 1:
                    second_part = self.audio_data.data[0:remaining_frames]
                    frames = np.concatenate([first_part, second_part])
                else:
                    second_part = self.audio_data.data[0:remaining_frames, :]
                    frames = np.concatenate([first_part, second_part], axis=0)
            else:
                # For ONE_SHOT and HOLD, truncate at end
                end_pos = total_frames
                if self.audio_data.num_channels == 1:
                    frames = self.audio_data.data[start_pos:end_pos]
                else:
                    frames = self.audio_data.data[start_pos:end_pos, :]
        else:
            # Normal case - extract frames
            if self.audio_data.num_channels == 1:
                frames = self.audio_data.data[start_pos:end_pos]
            else:
                frames = self.audio_data.data[start_pos:end_pos, :]

        # Apply volume
        if self.volume != 1.0:
            frames = frames * self.volume

        return frames

    @property
    def progress(self) -> float:
        """
        Get playback progress as fraction (0.0 to 1.0).

        Returns 0.0 if no audio data.
        """
        if self.audio_data is None or self.audio_data.num_frames == 0:
            return 0.0
        return min(self.position / self.audio_data.num_frames, 1.0)

    @property
    def time_elapsed(self) -> float:
        """Get elapsed playback time in seconds."""
        if self.audio_data is None:
            return 0.0
        return self.position / self.audio_data.sample_rate

    @property
    def time_remaining(self) -> float:
        """Get remaining playback time in seconds."""
        if self.audio_data is None:
            return 0.0
        remaining_frames = max(0, self.audio_data.num_frames - self.position)
        return remaining_frames / self.audio_data.sample_rate
