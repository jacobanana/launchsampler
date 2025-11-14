"""Device-agnostic audio playback engine for multi-pad samplers."""

import logging
from queue import Queue, Full
from threading import Lock
from typing import Dict, Optional

import numpy as np

from launchsampler.audio import AudioDevice, AudioMixer, SampleLoader
from launchsampler.audio.data import AudioData, PlaybackState
from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.models import Pad, PlaybackMode
from launchsampler.protocols import StateObserver

logger = logging.getLogger(__name__)


class SamplerEngine:
    """
    Audio playback engine for multi-pad samplers.

    Device-agnostic engine that manages audio playback for N pads.
    Works with any MIDI controller that provides pad triggers.

    Composes generic audio primitives (device, loader, mixer) with
    pad-based playback management.
    """

    def __init__(self, audio_device: AudioDevice, num_pads: int = 64):
        """
        Initialize sampler engine.

        Args:
            audio_device: Configured AudioDevice instance
            num_pads: Number of pads to manage (default: 64 for Launchpad)
        """
        self._device = audio_device
        self._num_pads = num_pads
        self._loader = SampleLoader(target_sample_rate=audio_device.sample_rate)
        self._mixer = AudioMixer(num_channels=audio_device.num_channels)

        # Application state
        self._audio_cache: Dict[str, AudioData] = {}  # path -> AudioData
        self._playback_states: Dict[int, PlaybackState] = {}  # pad_index -> PlaybackState
        self._master_volume = 1.0

        # State machine for event dispatch
        self._state_machine = SamplerStateMachine()

        # Thread safety
        self._lock = Lock()  # Only for sample loading/unloading, not for triggers

        # Lock-free trigger queue for low-latency pad triggering
        # Sized generously to handle burst inputs without blocking
        self._trigger_queue: Queue[tuple[str, int]] = Queue(maxsize=256)

        # Register audio callback
        self._device.set_callback(self._audio_callback)

    def load_sample(self, pad_index: int, pad: Pad, normalize: bool = True) -> bool:
        """
        Load audio sample for a pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)
            pad: Pad model with sample information
            normalize: Whether to normalize audio after loading

        Returns:
            True if loaded successfully, False otherwise
        """
        if pad_index < 0 or pad_index >= self._num_pads:
            logger.error(f"Invalid pad index: {pad_index} (valid: 0-{self._num_pads-1})")
            return False

        if not pad.is_assigned or pad.sample is None:
            return False

        path_str = str(pad.sample.path)

        try:
            # Check cache first
            if path_str not in self._audio_cache:
                audio_data = self._loader.load(pad.sample.path)
                self._audio_cache[path_str] = audio_data
            else:
                audio_data = self._audio_cache[path_str]

            # Normalize audio if needed
            if normalize:
                audio_data.normalize()

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
            logger.error(f"Error loading sample for pad {pad_index}: {e}")
            return False

    def unload_sample(self, pad_index: int) -> None:
        """
        Unload sample from pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].stop()
                self._playback_states[pad_index].audio_data = None

    def trigger_pad(self, pad_index: int) -> None:
        """
        Trigger playback for a pad.
        
        Lock-free implementation using queue for minimal latency.
        Safe to call from any thread (e.g., MIDI input thread).

        Args:
            pad_index: Pad index (0 to num_pads-1)
        """
        try:
            # Non-blocking queue write - if queue is full, drop the trigger
            # This should never happen with a 256-entry queue unless system is severely overloaded
            self._trigger_queue.put_nowait(("trigger", pad_index))
        except Full:
            logger.warning(f"Trigger queue full, dropped pad {pad_index} trigger")

    def release_pad(self, pad_index: int) -> None:
        """
        Release pad (for HOLD and LOOP modes).

        For HOLD mode: Stops playback immediately
        For LOOP mode: Stops looping
        For ONE_SHOT mode: Does nothing (sample plays fully)
        
        Lock-free implementation using queue for minimal latency.
        Safe to call from any thread (e.g., MIDI input thread).

        Args:
            pad_index: Pad index (0 to num_pads-1)
        """
        try:
            # Non-blocking queue write
            self._trigger_queue.put_nowait(("release", pad_index))
        except Full:
            logger.warning(f"Trigger queue full, dropped pad {pad_index} release")

    def stop_pad(self, pad_index: int) -> None:
        """
        Stop playback for a pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)
        """
        with self._lock:
            try:
                self._playback_states[pad_index].stop()
            except KeyError:
                pass

    def stop_all(self) -> None:
        """Stop all playing pads."""
        with self._lock:
            for state in self._playback_states.values():
                state.stop()

    def update_pad_volume(self, pad_index: int, volume: float) -> None:
        """
        Update volume for a pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)
            volume: New volume (0.0-1.0)
        """
        with self._lock:
            if pad_index in self._playback_states:
                self._playback_states[pad_index].volume = volume

    def update_pad_mode(self, pad_index: int, mode: PlaybackMode) -> None:
        """
        Update playback mode for a pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)
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

    def register_observer(self, observer: StateObserver) -> None:
        """
        Register an observer to receive playback state events.

        Args:
            observer: Object implementing StateObserver protocol
        """
        self._state_machine.register_observer(observer)

    def unregister_observer(self, observer: StateObserver) -> None:
        """
        Unregister an observer.

        Args:
            observer: Previously registered observer
        """
        self._state_machine.unregister_observer(observer)

    def is_pad_playing(self, pad_index: int) -> bool:
        """
        Check if a pad is currently playing.

        Args:
            pad_index: Pad index (0 to num_pads-1)

        Returns:
            True if pad is playing, False otherwise
        """
        return self._state_machine.is_pad_playing(pad_index)

    def get_playing_pads(self) -> list[int]:
        """
        Get list of all currently playing pad indices.

        Returns:
            List of pad indices that are currently playing
        """
        return self._state_machine.get_playing_pads()

    def get_playback_info(self, pad_index: int) -> Optional[dict]:
        """
        Get playback information for a pad.

        Args:
            pad_index: Pad index (0 to num_pads-1)

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

    def start(self) -> None:
        """Start audio device and begin playback."""
        self._device.start()

    def stop(self) -> None:
        """Stop audio device and all playback."""
        self.stop_all()
        self._device.stop()

    def _audio_callback(self, outdata: np.ndarray, frames: int) -> None:
        """
        Audio callback for mixing and rendering.

        Called by AudioDevice for each audio block.
        Processes trigger queue at the start for minimal latency.

        Args:
            outdata: Output buffer to fill
            frames: Number of frames requested
        """
        try:
            # Process all pending triggers from the lock-free queue
            # Do this FIRST before mixing to minimize trigger-to-sound latency
            while not self._trigger_queue.empty():
                try:
                    action, pad_index = self._trigger_queue.get_nowait()

                    # Check if pad exists in playback states (skip if not loaded)
                    if pad_index not in self._playback_states:
                        continue

                    # Direct state access without locking (audio thread is the only writer)
                    state = self._playback_states[pad_index]

                    if action == "trigger" and state.audio_data is not None:
                        was_playing = state.is_playing
                        state.start()

                        # Publish event
                        self._state_machine.on_pad_triggered(pad_index)
                        if state.is_playing and not was_playing:
                            self._state_machine.on_pad_playing(pad_index)

                    elif action == "release" and state.mode in (PlaybackMode.HOLD, PlaybackMode.LOOP):
                        if state.is_playing:
                            state.stop()
                            self._state_machine.on_pad_stopped(pad_index)

                except Exception as e:
                    logger.error(f"Error processing trigger queue for pad {pad_index}: {e}", exc_info=True)
                    continue

            # Track which pads were playing before mixing
            was_playing_before = {
                pad_index for pad_index, state in self._playback_states.items()
                if state.is_playing
            }

            # Get active playback states (no lock needed - audio thread owns playback state)
            active_states = [
                state for state in self._playback_states.values()
                if state.is_playing
            ]

            # Mix all active sources
            mixed = self._mixer.mix(active_states, frames)

            # Detect pads that finished playing (natural completion)
            for pad_index in was_playing_before:
                state = self._playback_states[pad_index]
                if not state.is_playing:
                    self._state_machine.on_pad_finished(pad_index)

            # Apply master volume
            if self._master_volume != 1.0:
                self._mixer.apply_master_volume(mixed, self._master_volume)

            # Soft clip to prevent harsh distortion
            self._mixer.soft_clip(mixed)

            # Copy to output buffer
            if self._device.num_channels == 1:
                outdata[:, 0] = mixed
            else:
                outdata[:] = mixed

        except Exception as e:
            # Log error and output silence to prevent audio stream crash
            logger.exception(f"Error in audio callback: {e}")
            outdata.fill(0.0)

    @property
    def is_running(self) -> bool:
        """Check if audio device is running."""
        return self._device.is_running

    @property
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        # Lock-free read - safe since we're just counting boolean flags
        return sum(1 for state in self._playback_states.values() if state.is_playing)

    @property
    def num_pads(self) -> int:
        """Get number of pads managed by this engine."""
        return self._num_pads

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
