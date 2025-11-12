"""Audio manager for handling playback with sounddevice."""

from pathlib import Path
from threading import Lock
from typing import Dict, Optional

import numpy as np
import sounddevice as sd

from ..models import Pad, PlaybackMode
from .data import AudioData, PlaybackState
from .loader import SampleLoader
from .mixer import AudioMixer


class AudioManager:
    """
    Manages audio playback using sounddevice.

    Handles:
    - Loading audio files
    - Managing playback states for 64 pads
    - Real-time mixing in audio callback
    - Thread-safe operations
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        buffer_size: int = 512,
        num_channels: int = 2,
        device: Optional[int] = None
    ):
        """
        Initialize audio manager.

        Args:
            sample_rate: Audio sample rate in Hz
            buffer_size: Audio buffer size in frames
            num_channels: Number of output channels (1=mono, 2=stereo)
            device: Output device ID (None for default)
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.num_channels = num_channels
        self.device = device

        # Audio components
        self.loader = SampleLoader(target_sample_rate=sample_rate)
        self.mixer = AudioMixer(num_channels=num_channels)

        # Storage
        self._audio_cache: Dict[str, AudioData] = {}  # path -> AudioData
        self._playback_states: Dict[int, PlaybackState] = {}  # pad_index -> PlaybackState

        # Thread safety
        self._lock = Lock()

        # Audio stream
        self._stream: Optional[sd.OutputStream] = None
        self._is_running = False

        # Master volume
        self._master_volume = 1.0

    def start(self) -> None:
        """Start audio stream."""
        if self._is_running:
            return

        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=self.num_channels,
            device=self.device,
            dtype=np.float32,
            callback=self._audio_callback
        )
        self._stream.start()
        self._is_running = True

    def stop(self) -> None:
        """Stop audio stream."""
        if not self._is_running:
            return

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._is_running = False

    def load_sample(self, pad_index: int, pad: Pad) -> bool:
        """
        Load audio sample for a pad.

        Args:
            pad_index: Pad index (0-63)
            pad: Pad model with sample information

        Returns:
            True if loaded successfully, False otherwise
        """
        if not pad.is_assigned or pad.sample is None:
            return False

        path_str = str(pad.sample.path)

        try:
            # Check cache first
            if path_str not in self._audio_cache:
                # Load audio file
                audio_data = self.loader.load(pad.sample.path)
                self._audio_cache[path_str] = audio_data
            else:
                audio_data = self._audio_cache[path_str]

            # Create or update playback state
            with self._lock:
                if pad_index not in self._playback_states:
                    self._playback_states[pad_index] = PlaybackState()

                state = self._playback_states[pad_index]
                state.audio_data = audio_data
                state.mode = pad.mode
                state.volume = pad.volume
                state.reset()

            return True

        except Exception as e:
            print(f"Error loading sample for pad {pad_index}: {e}")
            return False

    def unload_sample(self, pad_index: int) -> None:
        """
        Unload sample from pad.

        Args:
            pad_index: Pad index (0-63)
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].stop()
                self._playback_states[pad_index].audio_data = None

    def trigger_pad(self, pad_index: int) -> None:
        """
        Trigger playback for a pad.

        Args:
            pad_index: Pad index (0-63)
        """
        with self._lock:
            if pad_index in self._playback_states:
                state = self._playback_states[pad_index]
                if state.audio_data is not None:
                    state.start()

    def release_pad(self, pad_index: int) -> None:
        """
        Release pad (for HOLD mode).

        Args:
            pad_index: Pad index (0-63)
        """
        with self._lock:
            if pad_index in self._playback_states:
                state = self._playback_states[pad_index]
                if state.mode == PlaybackMode.HOLD:
                    state.stop()

    def stop_pad(self, pad_index: int) -> None:
        """
        Stop playback for a pad.

        Args:
            pad_index: Pad index (0-63)
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].stop()

    def stop_all(self) -> None:
        """Stop all playing pads."""
        with self._lock:
            for state in self._playback_states.values():
                state.stop()

    def update_pad_volume(self, pad_index: int, volume: float) -> None:
        """
        Update volume for a pad.

        Args:
            pad_index: Pad index (0-63)
            volume: New volume (0.0-1.0)
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].volume = volume

    def update_pad_mode(self, pad_index: int, mode: PlaybackMode) -> None:
        """
        Update playback mode for a pad.

        Args:
            pad_index: Pad index (0-63)
            mode: New playback mode
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].mode = mode

    def set_master_volume(self, volume: float) -> None:
        """
        Set master output volume.

        Args:
            volume: Master volume (0.0-1.0)
        """
        self._master_volume = max(0.0, min(1.0, volume))

    def get_playback_info(self, pad_index: int) -> Optional[dict]:
        """
        Get playback information for a pad.

        Args:
            pad_index: Pad index (0-63)

        Returns:
            Dictionary with playback info or None
        """
        with self._lock:
            if pad_index not in self._playback_states:
                return None

            state = self._playback_states[pad_index]
            return {
                'is_playing': state.is_playing,
                'progress': state.progress,
                'time_elapsed': state.time_elapsed,
                'time_remaining': state.time_remaining,
                'mode': state.mode.value,
                'volume': state.volume,
            }

    def clear_cache(self) -> None:
        """Clear audio cache (useful to free memory)."""
        with self._lock:
            self._audio_cache.clear()

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info,
        status
    ) -> None:
        """
        Audio callback called by sounddevice.

        Args:
            outdata: Output buffer to fill
            frames: Number of frames requested
            time_info: Timing information
            status: Status flags
        """
        if status:
            print(f"Audio callback status: {status}")

        # Get active playback states
        with self._lock:
            active_states = [
                state for state in self._playback_states.values()
                if state.is_playing
            ]

        # Mix all active sources
        mixed = self.mixer.mix(active_states, frames)

        # Apply master volume
        if self._master_volume != 1.0:
            self.mixer.apply_master_volume(mixed, self._master_volume)

        # Soft clip to prevent harsh distortion
        self.mixer.soft_clip(mixed)

        # Copy to output buffer
        if self.num_channels == 1:
            outdata[:, 0] = mixed
        else:
            outdata[:] = mixed

    @property
    def is_running(self) -> bool:
        """Check if audio stream is running."""
        return self._is_running

    @property
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        with self._lock:
            return sum(1 for state in self._playback_states.values() if state.is_playing)

    @staticmethod
    def list_devices() -> list:
        """
        List available audio devices.

        Returns:
            List of device dictionaries
        """
        return sd.query_devices()

    @staticmethod
    def get_default_device() -> int:
        """
        Get default output device ID.

        Returns:
            Device ID
        """
        return sd.default.device[1]  # Output device

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
