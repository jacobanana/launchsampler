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
from launchsampler.audio.data import AudioData
from launchsampler.core.sampler_engine import SamplerEngine
from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.devices import DeviceController
from launchsampler.models import AppConfig, Set, PlaybackMode
from launchsampler.protocols import PlaybackEvent, StateObserver, EditEvent, EditObserver, MidiEvent, MidiObserver
from launchsampler.utils import ObserverManager

logger = logging.getLogger(__name__)


class Player(StateObserver, EditObserver, MidiObserver):
    """
    Core player for Launchpad sampling.

    This class manages audio playback without any UI dependencies.
    It can be used in any application (TUI, GUI, CLI, headless).

    Implements:
    - StateObserver: for playback events from audio engine
    - EditObserver: for editing events from editor service
    - MidiObserver: for MIDI input events (triggered by orchestrator)

    Responsibilities:
    - Audio engine lifecycle
    - Playback state observation
    - Edit event observation and audio sync
    - MIDI input observation and audio triggering
    - Set loading into audio engine

    NOT responsible for:
    - MIDI controller lifecycle (managed by orchestrator)
    - UI rendering
    - User input beyond MIDI
    - Editing operations
    - File browsing
    """

    def __init__(self, config: AppConfig, state_machine: Optional[SamplerStateMachine] = None):
        """
        Initialize player.

        Args:
            config: Application configuration
            state_machine: Optional shared state machine for dependency injection.
                          If None, creates a new instance (for backward compatibility).
        """
        self.config = config
        self.current_set: Optional[Set] = None

        # State machine (injected or created)
        self._state_machine = state_machine or SamplerStateMachine()

        # Audio components
        self._audio_device: Optional[AudioDevice] = None
        self._engine: Optional[SamplerEngine] = None

        # Callbacks for external notification (deprecated - use register_state_observer)
        self._on_playback_change: Optional[Callable[[PlaybackEvent, int], None]] = None

        # State observers (multiple observers supported)
        self._state_observers = ObserverManager[StateObserver](observer_type_name="state")

        # State
        self._is_running = False
        logger.info("Player initialized")

    # =================================================================
    # Lifecycle
    # =================================================================

    def start(self, initial_set: Optional[Set] = None) -> bool:
        """
        Start player (audio only - MIDI is managed by orchestrator).

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

        self._is_running = True
        logger.info("Player started")
        return True

    def stop(self) -> None:
        """Stop player (audio only - MIDI is managed by orchestrator)."""
        if not self._is_running:
            return

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

            # Create engine with injected state machine
            self._engine = SamplerEngine(
                audio_device=self._audio_device,
                num_pads=64,  # Standard grid size for Launchpad devices
                state_machine=self._state_machine
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

    def stop_pad(self, pad_index: int) -> None:
        """
        Stop a specific pad immediately (works for all modes).

        Args:
            pad_index: Index of pad to stop (0-63)
        """
        if self._engine:
            self._engine.stop_pad(pad_index)

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
    # MidiObserver Protocol
    # =================================================================

    def on_midi_event(self, event: MidiEvent, pad_index: int, control: int = 0, value: int = 0) -> None:
        """
        Handle MIDI events from controller.

        This is called from the MIDI thread.

        Args:
            event: The MIDI event that occurred
            pad_index: Index of the pad (0-63), or -1 for connection/CC events
            control: MIDI CC control number (for CONTROL_CHANGE events)
            value: MIDI CC value (for CONTROL_CHANGE events)
        """
        if event == MidiEvent.NOTE_ON:
            # MIDI pad pressed - trigger audio if sample is assigned
            if self.current_set and pad_index >= 0:
                pad = self.current_set.launchpad.pads[pad_index]
                if pad.is_assigned:
                    self.trigger_pad(pad_index)
            else:
                logger.warning(f"MIDI NOTE_ON received but cannot trigger: current_set={self.current_set is not None}, pad_index={pad_index}")

        elif event == MidiEvent.NOTE_OFF:
            # MIDI pad released - release audio if mode supports it
            if self.current_set and pad_index >= 0:
                pad = self.current_set.launchpad.pads[pad_index]
                if pad.is_assigned and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
                    self.release_pad(pad_index)

        elif event == MidiEvent.CONTROL_CHANGE:
            # Handle panic button (stop all audio)
            if (control == self.config.panic_button_cc_control and
                value == self.config.panic_button_cc_value):
                logger.info(f"Panic button triggered via MIDI CC (control={control}, value={value})")
                self.stop_all()

        # Connection events don't require action from Player
        # (UI observers will handle status updates)

    # =================================================================
    # StateObserver Protocol
    # =================================================================

    def on_playback_event(self, event: PlaybackEvent, pad_index: int) -> None:
        """
        Handle playback events from audio engine.

        This is called from the audio thread, so we forward to all observers.
        """
        # Legacy callback support (deprecated)
        if self._on_playback_change:
            self._on_playback_change(event, pad_index)

        # Notify all state observers
        self._state_observers.notify('on_playback_event', event, pad_index)

    # =================================================================
    # EditObserver Protocol
    # =================================================================

    def on_edit_event(
        self,
        event: EditEvent,
        pad_indices: list[int],
        pads: list
    ) -> None:
        """
        Handle editing events and sync audio engine.

        This eliminates the need for manual _reload_pad() calls throughout
        the codebase. When any editing operation occurs (assign, clear, move,
        etc.), this observer automatically syncs the audio engine.

        Threading:
            Called from the UI thread (Textual's main loop).
            Delegates to SamplerEngine methods which use locks for thread safety.

        Args:
            event: The type of editing event
            pad_indices: List of affected pad indices
            pads: List of affected pad states (post-edit)
        """
        if not self._engine:
            return
        
        logger.debug(f"Player received edit event: {event.value} for pads {pad_indices}")
        
        for pad_index, pad in zip(pad_indices, pads):
            if event in (
                EditEvent.PAD_ASSIGNED,
                EditEvent.PAD_DUPLICATED,
                EditEvent.PAD_MODE_CHANGED
            ):
                # Reload sample into engine
                if pad.is_assigned:
                    logger.info(f"Loading sample '{pad.sample.name}' into pad {pad_index} (event: {event.value})")
                    self._engine.load_sample(pad_index, pad)
                else:
                    logger.info(f"Unloading pad {pad_index} (event: {event.value})")
                    self._engine.unload_sample(pad_index)
            
            elif event == EditEvent.PAD_MOVED:
                # For moves, reload both pads (source and target)
                if pad.is_assigned:
                    logger.info(f"Loading sample '{pad.sample.name}' into pad {pad_index} (moved)")
                    self._engine.load_sample(pad_index, pad)
                else:
                    logger.info(f"Unloading pad {pad_index} (moved)")
                    self._engine.unload_sample(pad_index)
            
            elif event == EditEvent.PAD_CLEARED:
                # Unload sample
                logger.info(f"Unloading pad {pad_index} (cleared)")
                self._engine.unload_sample(pad_index)
            
            elif event == EditEvent.PAD_VOLUME_CHANGED:
                # Update volume without reloading (more efficient)
                logger.debug(f"Updating volume for pad {pad_index} to {pad.volume}")
                self._engine.update_pad_volume(pad_index, pad.volume)
            
            elif event == EditEvent.PADS_CLEARED:
                # Multiple pads cleared - reload each
                logger.info(f"Unloading multiple pads: {pad_indices}")
                for idx, p in zip(pad_indices, pads):
                    self._engine.unload_sample(idx)
            
            # Note: PAD_NAME_CHANGED doesn't affect audio, no action needed

    # =================================================================
    # Callback Registration
    # =================================================================

    def register_state_observer(self, observer: StateObserver) -> None:
        """
        Register an observer for playback state events.

        Args:
            observer: Object implementing StateObserver protocol
        """
        self._state_observers.register(observer)

    def unregister_state_observer(self, observer: StateObserver) -> None:
        """
        Unregister a state observer.

        Args:
            observer: Previously registered observer
        """
        self._state_observers.unregister(observer)


    def set_playback_callback(self, callback: Callable[[PlaybackEvent, int], None]) -> None:
        """
        Register callback for playback events (DEPRECATED).

        Use register_state_observer() instead for proper observer pattern support.

        Args:
            callback: Function to call on playback events (from audio engine)
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
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        return self._engine.active_voices if self._engine else 0

    @property
    def audio_device_name(self) -> str:
        """Get name of audio device."""
        return self._audio_device.device_name if self._audio_device else "No Audio"

    @property
    def engine(self) -> Optional["SamplerEngine"]:
        """Get the sampler engine (read-only access)."""
        return self._engine

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

    def get_audio_data(self, pad_index: int) -> Optional[AudioData]:
        """
        Get audio waveform data for a pad (for visualization).

        Args:
            pad_index: Index of pad to get audio data for

        Returns:
            AudioData object if pad has audio loaded, None otherwise
        """
        if self._engine:
            return self._engine.get_audio_data(pad_index)
        return None

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
