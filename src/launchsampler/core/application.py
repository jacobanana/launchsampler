"""High-level application facade for the sampler."""

import logging
from pathlib import Path
from typing import Optional, Callable

from launchsampler.audio import AudioDevice
from launchsampler.devices.launchpad import LaunchpadController, LaunchpadDevice
from launchsampler.models import Launchpad, Set, AppConfig, PlaybackMode
from .sampler_engine import SamplerEngine

logger = logging.getLogger(__name__)


class SamplerApplication:
    """
    High-level application facade for the Launchpad sampler.

    Coordinates the audio engine (SamplerEngine) and device controller
    (LaunchpadController) with application configuration and lifecycle management.

    Separates concerns:
    - SamplerEngine: Handles audio playback (device-agnostic)
    - LaunchpadController: Handles MIDI communication (device-specific)
    - SamplerApplication: Coordinates lifecycle, events, and configuration
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        on_pad_event: Optional[Callable[[str, int], None]] = None
    ):
        """
        Initialize sampler application.

        Args:
            config: Application configuration (loads default if None)
            on_pad_event: Optional callback for pad events (event_type, pad_index)
                         event_type is "pressed" or "released"
        """
        self.config = config or AppConfig.load_or_default()
        self._on_pad_event = on_pad_event

        # Components (created on start)
        self._audio_device: Optional[AudioDevice] = None
        self._engine: Optional[SamplerEngine] = None
        self._controller: Optional[LaunchpadController] = None

        # State
        self.launchpad: Optional[Launchpad] = None
        self.current_set: Optional[Set] = None
        self._is_running = False

    def load_samples_from_directory(
        self,
        samples_dir: Optional[Path] = None,
        auto_configure: bool = True,
        default_volume: float = 0.1
    ) -> Launchpad:
        """
        Load samples from directory using Launchpad.from_sample_directory factory.

        Args:
            samples_dir: Directory with samples (uses config default if None)
            auto_configure: Infer playback mode from filename
            default_volume: Default volume for all pads

        Returns:
            Configured Launchpad instance

        Raises:
            ValueError: If directory doesn't exist or contains no audio files
        """
        dir_path = samples_dir or self.config.samples_dir

        self.launchpad = Launchpad.from_sample_directory(
            samples_dir=dir_path,
            auto_configure=auto_configure,
            default_volume=default_volume
        )

        logger.info(f"Loaded {len(self.launchpad.assigned_pads)} samples from {dir_path}")
        return self.launchpad

    def load_set(self, set_name: str) -> Set:
        """
        Load a saved set from disk.

        Args:
            set_name: Name of the set to load (without .json extension)

        Returns:
            Loaded Set instance

        Raises:
            FileNotFoundError: If set file doesn't exist
        """
        set_path = self.config.sets_dir / f"{set_name}.json"
        if not set_path.exists():
            raise FileNotFoundError(f"Set not found: {set_path}")

        saved_set = Set.load_from_file(set_path)
        self.launchpad = saved_set.launchpad
        self.current_set = saved_set

        logger.info(f"Loaded set: {set_name}")
        return saved_set

    def save_current_set(self, name: str) -> None:
        """
        Save current configuration as a set.

        Args:
            name: Name for the set (without .json extension)

        Raises:
            RuntimeError: If no configuration is loaded
        """
        if not self.launchpad:
            raise RuntimeError("No configuration loaded. Load samples first.")

        saved_set = Set(name=name, launchpad=self.launchpad)

        self.config.ensure_directories()
        save_path = self.config.sets_dir / f"{name}.json"
        saved_set.save_to_file(save_path)

        self.current_set = saved_set
        logger.info(f"Saved set: {name} to {save_path}")

    def start(
        self,
        audio_device: Optional[int] = None,
        sample_rate: Optional[int] = None,
        buffer_size: Optional[int] = None,
        low_latency: bool = True
    ) -> None:
        """
        Start the sampler (audio + MIDI).

        Args:
            audio_device: Audio device ID (None = default)
            sample_rate: Sample rate in Hz (None = use config)
            buffer_size: Buffer size in frames (None = use config)
            low_latency: Enable low-latency mode

        Raises:
            RuntimeError: If no samples are loaded
            ValueError: If audio device configuration is invalid
        """
        if self._is_running:
            logger.warning("Sampler already running")
            return

        if not self.launchpad:
            raise RuntimeError("No samples loaded. Call load_samples_from_directory() or load_set() first")

        # Create audio device
        self._audio_device = AudioDevice(
            device=audio_device,
            sample_rate=sample_rate or self.config.sample_rate,
            buffer_size=buffer_size or self.config.buffer_size,
            low_latency=low_latency
        )

        # Create engine with Launchpad-specific pad count
        self._engine = SamplerEngine(
            audio_device=self._audio_device,
            num_pads=LaunchpadDevice.NUM_PADS
        )

        # Create controller
        self._controller = LaunchpadController(poll_interval=2.0)

        # Load samples into audio engine
        loaded_count = 0
        for i, pad in enumerate(self.launchpad.pads):
            if pad.is_assigned:
                success = self._engine.load_sample(i, pad)
                if success:
                    loaded_count += 1
                else:
                    logger.error(f"Failed to load sample for pad {i}")

        logger.info(f"Loaded {loaded_count}/{len(self.launchpad.assigned_pads)} samples into engine")

        # Wire up event handlers
        self._controller.on_pad_pressed(self._handle_pad_pressed)
        self._controller.on_pad_released(self._handle_pad_released)

        # Start everything
        self._engine.start()
        self._controller.start()

        self._is_running = True
        logger.info("Sampler application started")

    def stop(self) -> None:
        """Stop the sampler and cleanup resources."""
        if not self._is_running:
            return

        if self._controller:
            self._controller.stop()

        if self._engine:
            self._engine.stop()

        self._is_running = False
        logger.info("Sampler application stopped")

    def _handle_pad_pressed(self, pad_index: int) -> None:
        """Internal handler for pad press events."""
        if not self._engine or not self.launchpad:
            return

        pad = self.launchpad.pads[pad_index]
        if pad.is_assigned:
            self._engine.trigger_pad(pad_index)

            # Notify external callback
            if self._on_pad_event:
                self._on_pad_event("pressed", pad_index)

            logger.debug(f"Pad {pad_index} pressed: {pad.sample.name}")

    def _handle_pad_released(self, pad_index: int) -> None:
        """Internal handler for pad release events."""
        if not self._engine or not self.launchpad:
            return

        pad = self.launchpad.pads[pad_index]
        if pad.is_assigned and pad.mode in (PlaybackMode.LOOP, PlaybackMode.HOLD):
            self._engine.release_pad(pad_index)

            # Notify external callback
            if self._on_pad_event:
                self._on_pad_event("released", pad_index)

            logger.debug(f"Pad {pad_index} released")

    @property
    def is_running(self) -> bool:
        """Check if sampler is running."""
        return self._is_running

    @property
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        if self._engine:
            return self._engine.active_voices
        return 0

    @property
    def is_connected(self) -> bool:
        """Check if MIDI controller is connected."""
        if self._controller:
            return self._controller.is_connected
        return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
