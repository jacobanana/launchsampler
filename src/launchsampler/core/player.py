"""
Core player logic - UI-agnostic.

This can be used in:
- TUI application
- GUI application
- Headless server
- CLI tool
- Test environment
"""

from typing import Optional, Callable
from pathlib import Path
import logging

from launchsampler.audio import AudioDevice
from launchsampler.core.sampler_engine import SamplerEngine
from launchsampler.devices.launchpad import LaunchpadController, LaunchpadDevice
from launchsampler.models import AppConfig, Set, PlaybackMode
from launchsampler.protocols import PlaybackEvent, StateObserver

logger = logging.getLogger(__name__)


class Player(StateObserver):
    """
    Core player for Launchpad sampling.

    This class manages audio and MIDI without any UI dependencies.
    It can be used in any application (TUI, GUI, CLI, headless).

    Responsibilities:
    - Audio engine lifecycle
    - MIDI controller lifecycle
    - Playback state observation
    - Set loading into audio engine
    - Trigger routing

    NOT responsible for:
    - UI rendering
    - User input beyond MIDI
    - Editing operations
    - File browsing
    """

    def __init__(self, config: AppConfig):
        """
        Initialize player.

        Args:
            config: Application configuration
        """
        self.config = config
        self.current_set: Optional[Set] = None

        # Audio components
        self._audio_device: Optional[AudioDevice] = None
        self._engine: Optional[SamplerEngine] = None

        # MIDI components
        self._midi: Optional[LaunchpadController] = None

        # Callbacks for external notification
        self._on_playback_change: Optional[Callable[[PlaybackEvent, int], None]] = None

        # State
        self._is_running = False

    # =================================================================
    # Lifecycle
    # =================================================================

    def start(self, initial_set: Optional[Set] = None) -> bool:
        """
        Start player (audio + MIDI).

        Args:
            initial_set: Optional set to load on startup

        Returns:
            True if started successfully
        """
        if self._is_running:
            logger.warning("Player already running")
            return True

        # Load initial set if provided
        if initial_set:
            self.current_set = initial_set

        # Start audio engine
        if not self._start_audio():
            logger.error("Failed to start audio")
            return False

        # Start MIDI controller (optional, don't fail if unavailable)
        self._start_midi()

        self._is_running = True
        logger.info("Player started")
        return True

    def stop(self) -> None:
        """Stop player (audio + MIDI)."""
        if not self._is_running:
            return

        self._stop_midi()
        self._stop_audio()

        self._is_running = False
        logger.info("Player stopped")

    def _start_audio(self) -> bool:
        """Start audio device and engine."""
        try:
            # Create audio device
            self._audio_device = AudioDevice(
                device=self.config.default_audio_device,
                buffer_size=self.config.default_buffer_size,
                low_latency=True
            )

            # Create engine
            self._engine = SamplerEngine(
                audio_device=self._audio_device,
                num_pads=LaunchpadDevice.NUM_PADS
            )

            # Register as observer
            self._engine.register_observer(self)

            # Load current set if available
            if self.current_set:
                self._load_set_into_engine(self.current_set)

            # Start audio
            self._engine.start()
            logger.info("Audio engine started")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio: {e}", exc_info=True)
            self._audio_device = None
            self._engine = None
            return False

    def _stop_audio(self) -> None:
        """Stop audio engine and device."""
        if self._engine:
            self._engine.stop()
            self._engine = None
        self._audio_device = None
        logger.info("Audio engine stopped")

    def _start_midi(self) -> bool:
        """Start MIDI controller."""
        try:
            self._midi = LaunchpadController(
                poll_interval=self.config.midi_poll_interval
            )

            # Wire up event handlers
            self._midi.on_pad_pressed(self._on_pad_pressed)
            self._midi.on_pad_released(self._on_pad_released)

            # Start controller
            self._midi.start()
            logger.info("MIDI controller started")
            return True

        except Exception as e:
            logger.warning(f"MIDI not available: {e}")
            self._midi = None
            return False

    def _stop_midi(self) -> None:
        """Stop MIDI controller."""
        if self._midi:
            self._midi.stop()
            self._midi = None
            logger.info("MIDI controller stopped")

    # =================================================================
    # Set Management
    # =================================================================

    def load_set(self, set_obj: Set) -> None:
        """
        Load a new set.

        Args:
            set_obj: Set to load
        """
        self.current_set = set_obj

        # Load into engine if running
        if self._engine and self._is_running:
            self._load_set_into_engine(set_obj)

        logger.info(f"Loaded set: {set_obj.name} with {len(set_obj.launchpad.assigned_pads)} samples")

    def _load_set_into_engine(self, set_obj: Set) -> None:
        """Load all pads from set into audio engine."""
        if not self._engine:
            return

        loaded_count = 0
        for pad_index, pad in enumerate(set_obj.launchpad.pads):
            if pad.is_assigned:
                if self._engine.load_sample(pad_index, pad):
                    loaded_count += 1

        logger.info(f"Loaded {loaded_count} samples into engine")

    # =================================================================
    # Playback Control
    # =================================================================

    def trigger_pad(self, pad_index: int) -> None:
        """
        Trigger a pad (from any source: MIDI, keyboard, UI, etc).

        Args:
            pad_index: Index of pad to trigger (0-63)
        """
        if self._engine:
            self._engine.trigger_pad(pad_index)

    def release_pad(self, pad_index: int) -> None:
        """
        Release a pad (for HOLD/LOOP modes).

        Args:
            pad_index: Index of pad to release (0-63)
        """
        if self._engine:
            self._engine.release_pad(pad_index)

    def stop_all(self) -> None:
        """Stop all playing pads."""
        if self._engine:
            self._engine.stop_all()

    def set_master_volume(self, volume: float) -> None:
        """
        Set master output volume.

        Args:
            volume: Master volume (0.0-1.0)
        """
        if self._engine:
            self._engine.set_master_volume(volume)

    # =================================================================
    # MIDI Event Handlers (private)
    # =================================================================

    def _on_pad_pressed(self, pad_index: int) -> None:
        """Handle MIDI pad press."""
        if not self.current_set:
            return

        pad = self.current_set.launchpad.pads[pad_index]
        
        # Always provide UI feedback
        if self._on_playback_change:
            self._on_playback_change(PlaybackEvent.PAD_PLAYING, pad_index)
        
        # Only trigger audio if sample is assigned
        if pad.is_assigned:
            self.trigger_pad(pad_index)

    def _on_pad_released(self, pad_index: int) -> None:
        """Handle MIDI pad release."""
        if not self.current_set:
            return

        pad = self.current_set.launchpad.pads[pad_index]
        
        # Always provide UI feedback
        if self._on_playback_change:
            self._on_playback_change(PlaybackEvent.PAD_STOPPED, pad_index)
        
        # Only release audio if sample is assigned and mode supports it
        if pad.is_assigned and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
            self.release_pad(pad_index)

    # =================================================================
    # StateObserver Protocol
    # =================================================================

    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback events from audio engine.

        This is called from the audio thread, so we just forward to callback.
        """
        if self._on_playback_change:
            self._on_playback_change(event, pad_index)

    # =================================================================
    # Callback Registration
    # =================================================================

    def set_playback_callback(self, callback: Callable[[PlaybackEvent, int], None]) -> None:
        """
        Register callback for playback events.

        Args:
            callback: Function to call on playback events
        """
        self._on_playback_change = callback

    # =================================================================
    # Query Methods
    # =================================================================

    @property
    def is_running(self) -> bool:
        """Check if player is running."""
        return self._is_running

    @property
    def is_midi_connected(self) -> bool:
        """Check if MIDI is connected."""
        return self._midi is not None and self._midi.is_connected

    @property
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        return self._engine.active_voices if self._engine else 0

    @property
    def audio_device_name(self) -> str:
        """Get name of audio device."""
        return self._audio_device.device_name if self._audio_device else "No Audio"

    @property
    def midi_device_name(self) -> str:
        """Get name of MIDI device."""
        return self._midi.device_name if self._midi else "No MIDI"

    def is_pad_playing(self, pad_index: int) -> bool:
        """
        Check if a pad is currently playing.

        Args:
            pad_index: Index of pad to check

        Returns:
            True if pad is playing
        """
        return self._engine.is_pad_playing(pad_index) if self._engine else False

    def get_playing_pads(self) -> list[int]:
        """
        Get list of all currently playing pads.

        Returns:
            List of pad indices
        """
        return self._engine.get_playing_pads() if self._engine else []

    # =================================================================
    # Context Manager
    # =================================================================

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
