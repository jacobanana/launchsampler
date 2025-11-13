"""Sampler service for managing audio/MIDI with edit and play modes."""

import logging
from typing import Optional, Callable, Literal

from launchsampler.core import SamplerApplication
from launchsampler.audio import AudioDevice
from launchsampler.core.sampler_engine import SamplerEngine
from launchsampler.devices.launchpad import LaunchpadController
from launchsampler.models import Launchpad, AppConfig

logger = logging.getLogger(__name__)


class SamplerService:
    """
    Manages sampler application with Edit and Play modes.

    This service wraps SamplerApplication and provides mode switching:
    - Edit Mode: Audio preview only (no MIDI interference)
    - Play Mode: Full MIDI integration for performance

    The service can hot-upgrade from edit to play mode without audio glitches.
    """

    def __init__(
        self,
        launchpad: Launchpad,
        config: AppConfig,
        on_pad_event: Optional[Callable[[str, int], None]] = None
    ):
        """
        Initialize the sampler service.

        Args:
            launchpad: The Launchpad model with samples
            config: Application configuration
            on_pad_event: Optional callback for MIDI events (event_type, pad_index)
        """
        self.launchpad = launchpad
        self.config = config
        self._on_pad_event = on_pad_event

        # Internal state
        self._app: Optional[SamplerApplication] = None
        self._mode: Literal["stopped", "edit", "play"] = "stopped"

    def start_edit_mode(self) -> bool:
        """
        Start audio-only preview (edit mode).

        Creates SamplerApplication but only starts the audio engine,
        not the MIDI controller. This allows testing samples without
        MIDI interference during editing.

        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Create SamplerApplication instance
            self._app = SamplerApplication(config=self.config)
            self._app.launchpad = self.launchpad

            # Manually start audio engine only (skip MIDI controller)
            # This is composition - we're using SamplerApplication's components
            self._app._audio_device = AudioDevice(
                device=self.config.default_audio_device,
                buffer_size=512  # Low latency for preview
            )
            self._app._engine = SamplerEngine(
                self._app._audio_device,
                num_pads=64
            )

            # Load all assigned samples
            for i, pad in enumerate(self.launchpad.pads):
                if pad.is_assigned:
                    self._app._engine.load_sample(i, pad)

            # Start audio engine
            self._app._engine.start()
            self._app._is_running = True

            self._mode = "edit"
            logger.info("Started edit mode (audio preview)")
            return True

        except Exception as e:
            logger.error(f"Failed to start edit mode: {e}", exc_info=True)
            return False

    def start_play_mode(self) -> bool:
        """
        Start or upgrade to play mode (audio + MIDI).

        If already in edit mode, hot-upgrades by adding MIDI controller
        to running audio engine. Otherwise, cold-starts with full
        SamplerApplication.

        Returns:
            True if started successfully, False otherwise
        """
        if self._mode == "edit" and self._app:
            # Hot upgrade: add MIDI to running audio
            return self._upgrade_to_play_mode()
        elif self._mode == "stopped":
            # Cold start: full SamplerApplication
            return self._cold_start_play_mode()
        else:
            logger.warning(f"Cannot start play mode from {self._mode} state")
            return False

    def _upgrade_to_play_mode(self) -> bool:
        """Upgrade from edit to play mode (add MIDI to running audio)."""
        try:
            if not self._app:
                return False

            # Create and start MIDI controller
            # Using SamplerApplication's internal handlers for consistency
            self._app._controller = LaunchpadController(
                poll_interval=self.config.midi_poll_interval
            )

            # Wire up event handlers
            self._app._controller.on_pad_pressed(self._handle_pad_pressed)
            self._app._controller.on_pad_released(self._handle_pad_released)

            # Start MIDI controller
            self._app._controller.start()

            self._mode = "play"
            logger.info("Upgraded to play mode (added MIDI)")
            return True

        except Exception as e:
            logger.error(f"Failed to upgrade to play mode: {e}", exc_info=True)
            return False

    def _cold_start_play_mode(self) -> bool:
        """Cold start in play mode (full SamplerApplication)."""
        try:
            # Use full SamplerApplication lifecycle
            self._app = SamplerApplication(
                config=self.config,
                on_pad_event=self._on_pad_event
            )
            self._app.launchpad = self.launchpad

            # Full start (audio + MIDI)
            self._app.start()

            self._mode = "play"
            logger.info("Started play mode (audio + MIDI)")
            return True

        except Exception as e:
            logger.error(f"Failed to start play mode: {e}", exc_info=True)
            return False

    def stop_play_mode(self) -> bool:
        """
        Downgrade from play to edit mode (remove MIDI, keep audio).

        Returns:
            True if downgraded successfully, False otherwise
        """
        if self._mode == "play" and self._app and self._app._controller:
            try:
                # Stop and remove MIDI controller
                self._app._controller.stop()
                self._app._controller = None

                self._mode = "edit"
                logger.info("Downgraded to edit mode (removed MIDI)")
                return True

            except Exception as e:
                logger.error(f"Failed to stop play mode: {e}", exc_info=True)
                return False

        return False

    def stop(self) -> None:
        """Stop everything (audio + MIDI)."""
        if self._app:
            try:
                self._app.stop()
                self._mode = "stopped"
                logger.info("Stopped sampler service")
            except Exception as e:
                logger.error(f"Error stopping sampler service: {e}", exc_info=True)

    def trigger_pad(self, pad_index: int) -> None:
        """
        Trigger a pad (works in both edit and play modes).

        Args:
            pad_index: Index of pad to trigger (0-63)
        """
        if self._app and self._app._engine:
            self._app._engine.trigger_pad(pad_index)

    def release_pad(self, pad_index: int) -> None:
        """
        Release a pad (for HOLD and LOOP modes).

        Args:
            pad_index: Index of pad to release (0-63)
        """
        if self._app and self._app._engine:
            self._app._engine.release_pad(pad_index)

    def reload_pad(self, pad_index: int) -> None:
        """
        Reload a pad after editing (reloads sample into engine).

        Args:
            pad_index: Index of pad to reload (0-63)
        """
        if self._app and self._app._engine:
            pad = self.launchpad.pads[pad_index]
            if pad.is_assigned:
                self._app._engine.load_sample(pad_index, pad)
            else:
                self._app._engine.unload_sample(pad_index)

    def reload_all(self) -> None:
        """Reload all pads (after loading a new set)."""
        if self._app and self._app._engine:
            for i in range(64):
                self.reload_pad(i)

    def stop_all(self) -> None:
        """Stop all playing pads."""
        if self._app and self._app._engine:
            self._app._engine.stop_all()

    def _handle_pad_pressed(self, pad_index: int) -> None:
        """
        Handle MIDI pad press event (play mode only).

        This delegates to SamplerApplication's handler and also
        notifies the callback for UI feedback.
        """
        # Let SamplerApplication handle the audio trigger
        if self._app:
            self._app._handle_pad_pressed(pad_index)

        # Notify UI callback for visual feedback
        if self._on_pad_event:
            self._on_pad_event("pressed", pad_index)

    def _handle_pad_released(self, pad_index: int) -> None:
        """
        Handle MIDI pad release event (play mode only).

        This delegates to SamplerApplication's handler and also
        notifies the callback for UI feedback.
        """
        # Let SamplerApplication handle the release
        if self._app:
            self._app._handle_pad_released(pad_index)

        # Notify UI callback for visual feedback
        if self._on_pad_event:
            self._on_pad_event("released", pad_index)

    @property
    def mode(self) -> str:
        """Get current mode (stopped, edit, or play)."""
        return self._mode

    @property
    def is_running(self) -> bool:
        """Check if sampler is running (any mode)."""
        return self._mode != "stopped" and self._app is not None

    @property
    def is_connected(self) -> bool:
        """Check if MIDI controller is connected (play mode only)."""
        if self._mode == "play" and self._app:
            return self._app.is_connected
        return False

    @property
    def active_voices(self) -> int:
        """Get number of currently playing voices."""
        if self._app:
            return self._app.active_voices
        return 0

    def is_pad_playing(self, pad_index: int) -> bool:
        """
        Check if a pad is currently playing.

        Args:
            pad_index: Index of pad to check (0-63)

        Returns:
            True if pad is currently playing, False otherwise
        """
        if self._app and self._app._engine:
            playback_info = self._app._engine.get_playback_info(pad_index)
            return playback_info.get('is_playing', False) if playback_info else False
        return False
