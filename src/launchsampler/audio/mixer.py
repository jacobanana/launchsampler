"""Audio mixer for combining multiple playback states."""

from typing import List

import numpy as np
import numpy.typing as npt

from .data import PlaybackState


class AudioMixer:
    """
    Mix multiple audio sources into a single output.

    Thread-safe for use in audio callbacks.
    """

    def __init__(self, num_channels: int = 2):
        """
        Initialize audio mixer.

        Args:
            num_channels: Number of output channels (1=mono, 2=stereo)
        """
        self.num_channels = num_channels

    def mix(
        self,
        playback_states: List[PlaybackState],
        num_frames: int
    ) -> npt.NDArray[np.float32]:
        """
        Mix multiple playback states into a single buffer.

        Args:
            playback_states: List of PlaybackState objects to mix
            num_frames: Number of frames to generate

        Returns:
            Mixed audio buffer (num_frames, num_channels) or (num_frames,) for mono
        """
        # Create output buffer
        if self.num_channels == 1:
            output = np.zeros(num_frames, dtype=np.float32)
        else:
            output = np.zeros((num_frames, self.num_channels), dtype=np.float32)

        # Mix each playing source
        for state in playback_states:
            if not state.is_playing or state.audio_data is None:
                continue

            # Get frames from this source
            frames = state.get_frames(num_frames)
            if frames is None:
                continue

            # Handle channel mismatch
            frames_to_add = self._match_channels(frames, state.audio_data.num_channels)

            # Add to output (clip to available length)
            add_length = min(len(frames_to_add), num_frames)
            if self.num_channels == 1:
                output[:add_length] += frames_to_add[:add_length]
            else:
                output[:add_length, :] += frames_to_add[:add_length, :]

            # Advance the playback position
            state.advance(add_length)

        return output

    def _match_channels(
        self,
        frames: npt.NDArray[np.float32],
        source_channels: int
    ) -> npt.NDArray[np.float32]:
        """
        Convert audio frames to match output channel count.

        Args:
            frames: Input audio frames
            source_channels: Number of channels in source

        Returns:
            Audio frames with matching channel count
        """
        # Already matches
        if source_channels == self.num_channels:
            return frames

        # Mono to stereo
        if source_channels == 1 and self.num_channels == 2:
            return np.column_stack([frames, frames])

        # Stereo to mono
        if source_channels == 2 and self.num_channels == 1:
            return np.mean(frames, axis=1, dtype=np.float32)

        # Multi-channel to mono
        if source_channels > 1 and self.num_channels == 1:
            return np.mean(frames, axis=1, dtype=np.float32)

        # Multi-channel to stereo (take first 2 channels)
        if source_channels > 2 and self.num_channels == 2:
            return frames[:, :2]

        return frames

    @staticmethod
    def apply_master_volume(
        buffer: npt.NDArray[np.float32],
        volume: float
    ) -> None:
        """
        Apply master volume to buffer in-place.

        Args:
            buffer: Audio buffer to modify
            volume: Volume multiplier (0.0 to 1.0)
        """
        if volume != 1.0:
            buffer *= volume

    @staticmethod
    def clip(buffer: npt.NDArray[np.float32]) -> None:
        """
        Clip audio buffer to valid range [-1.0, 1.0] in-place.

        Args:
            buffer: Audio buffer to clip
        """
        np.clip(buffer, -1.0, 1.0, out=buffer)

    @staticmethod
    def soft_clip(buffer: npt.NDArray[np.float32]) -> None:
        """
        Apply soft clipping (tanh) to prevent harsh distortion.

        Args:
            buffer: Audio buffer to soft clip
        """
        np.tanh(buffer, out=buffer)
