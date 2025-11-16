"""Generic audio device and stream management."""

import logging
import sys
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioDevice:
    """
    Generic low-latency audio output device and stream management.

    Handles device querying, validation, and stream lifecycle.
    No application-specific logic - purely generic audio I/O.
    """

    def __init__(
        self,
        buffer_size: int = 128,
        num_channels: int = 2,
        device: Optional[int] = None,
        low_latency: bool = True
    ):
        """
        Initialize audio device.

        Args:
            sample_rate: Audio sample rate in Hz
            buffer_size: Audio buffer size in frames (lower = less latency)
            num_channels: Number of output channels (1=mono, 2=stereo)
            device: Output device ID (None for default)
            low_latency: Enable low-latency optimizations

        Raises:
            ValueError: If device doesn't use low-latency API
        """
        self.buffer_size = buffer_size
        self.num_channels = num_channels
        self.low_latency = low_latency

        # Validate device if specified
        if device is not None:
            self._validate_device(device)

        self.device = device

        # Stream state
        self._stream: Optional[sd.OutputStream] = None
        self._is_running = False
        self._callback: Optional[Callable[[np.ndarray, int], None]] = None

    @staticmethod
    def _get_platform_apis() -> tuple[list[str], str]:
        """
        Get platform-specific low-latency APIs.

        - Windows: ASIO, WASAPI
        - macOS: Core Audio
        - Linux: ALSA, JACK

        Returns:
            Tuple of (api_list, api_names_string)
        """
        if sys.platform == 'win32':
            return ['ASIO', 'WASAPI'], "ASIO/WASAPI"
        elif sys.platform == 'darwin':
            return ['Core Audio'], "Core Audio"
        else:
            return ['ALSA', 'JACK'], "ALSA/JACK"

    @staticmethod
    def _is_valid_device(device_id: int) -> tuple[bool, str, str]:
        """
        Check if device uses a low-latency audio API.

        Args:
            device_id: Device ID to check

        Returns:
            Tuple of (is_valid, hostapi_name, device_name)

        Raises:
            ValueError: If device_id is invalid
        """
        try:
            device_info = sd.query_devices(device_id)
            hostapi_info = sd.query_hostapis(device_info['hostapi'])
            hostapi_name = hostapi_info['name']
            device_name = device_info['name']

            low_latency_apis, _ = AudioDevice._get_platform_apis()
            is_valid = any(api in hostapi_name for api in low_latency_apis)
            return is_valid, hostapi_name, device_name

        except Exception:
            raise ValueError(
                f"Invalid device ID: {device_id}. "
                f"Use AudioDevice.list_output_devices() to list available devices."
            )

    def _validate_device(self, device_id: int) -> None:
        """
        Validate that device uses a low-latency audio API.

        Args:
            device_id: Device ID to validate

        Raises:
            ValueError: If device doesn't use a low-latency API
        """
        is_valid, hostapi_name, device_name = self._is_valid_device(device_id)

        if not is_valid:
            _, api_names = AudioDevice._get_platform_apis()
            raise ValueError(
                f"Device '{device_name}' uses Host API '{hostapi_name}'. "
                f"Only {api_names} devices are supported for low-latency playback. "
                f"Use AudioDevice.list_output_devices() to find suitable devices."
            )

        logger.info(f"Validated device: {device_name} ({hostapi_name})")

    def set_callback(self, callback: Callable[[np.ndarray, int], None]) -> None:
        """
        Set audio callback function.

        The callback will be called with (outdata, frames) for each audio block.

        Args:
            callback: Function(outdata: np.ndarray, frames: int) -> None
        """
        self._callback = callback

    def start(self) -> None:
        """Start audio stream."""
        if self._is_running:
            return

        if self._callback is None:
            raise RuntimeError("No audio callback set. Call set_callback() first.")

        device_id = self.device or sd.default.device[1]
        self._validate_low_latency_device(device_id)
        self._log_device_info(device_id)

        # Select stream configuration
        stream_kwargs = self._get_stream_config(device_id)

        # Try to start the stream
        self._start_stream(stream_kwargs)


    def stop(self) -> None:
        """Stop audio stream."""
        if not self._is_running:
            return

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._is_running = False

    def _validate_low_latency_device(self, device_id: int) -> None:
        """Ensure the selected device supports a low-latency API."""
        is_valid, hostapi_name, device_name = self._is_valid_device(device_id)
        if not is_valid:
            _, api_names = self._get_platform_apis()
            raise ValueError(
                f"Device '{device_name}' uses Host API '{hostapi_name}'. "
                f"Only {api_names} devices are supported for low-latency playback."
            )
        logger.info(f"Validated device: {device_name} ({hostapi_name})")

    def _log_device_info(self, device_id: int) -> None:
        """Log details about the chosen audio device."""
        device_info = sd.query_devices(device_id)
        hostapi_info = sd.query_hostapis(device_info['hostapi'])
        logger.info(f"Audio device: {device_info['name']}")
        logger.info(f"  Host API: {hostapi_info['name']}")
        logger.info(f"  Max output channels: {device_info['max_output_channels']}")
        logger.info(f"  Default sample rate: {device_info['default_samplerate']} Hz")
        logger.info(f"  Default low latency: {device_info['default_low_output_latency']*1000:.1f}ms")

    def _get_stream_config(self, device_id: int) -> dict:
        """Return appropriate stream configuration for the platform/device."""
        hostapi_name = sd.query_hostapis(sd.query_devices(device_id)['hostapi'])['name']
        is_asio = 'ASIO' in hostapi_name
        is_wasapi = 'WASAPI' in hostapi_name

        base_config = dict(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=self.num_channels,
            device=device_id,
            dtype=np.float32,
            callback=self._audio_callback,
        )

        # ASIO devices
        if is_asio:
            logger.debug("Using ASIO configuration")
            return base_config

        # WASAPI exclusive mode if available (Windows only)
        if is_wasapi and self.low_latency and hasattr(sd, 'WasapiSettings'):
            try:
                base_config['extra_settings'] = sd.WasapiSettings(exclusive=True)
                base_config['prime_output_buffers_using_stream_callback'] = False
                logger.debug("Using WASAPI exclusive mode configuration")
                return base_config
            except sd.PortAudioError:
                logger.info("WASAPI exclusive mode not available, falling back to shared mode")

        logger.debug("Using standard shared mode configuration")
        return base_config

    def _start_stream(self, config: dict) -> None:
        """Create and start the stream with the given configuration."""

        self._stream = sd.OutputStream(**config)
        self._stream.start()
        self._is_running = True

        latency_ms = self._stream.latency * 1000
        buffer_ms = self.buffer_size / self.sample_rate * 1000
        logger.info("Audio stream started")
        logger.info(f"  Buffer size: {self.buffer_size} frames ({buffer_ms:.1f}ms)")
        logger.info(f"  Total latency: {latency_ms:.1f}ms")


    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info,
        status
    ) -> None:
        """
        Internal audio callback called by sounddevice.

        Delegates to user callback if set.
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        if self._callback:
            self._callback(outdata, frames)
        else:
            # Fill with silence if no callback
            outdata.fill(0)

    @property
    def is_running(self) -> bool:
        """Check if audio stream is running."""
        return self._is_running

    @property
    def latency(self) -> float:
        """Get current stream latency in seconds."""
        if self._stream:
            return self._stream.latency
        return 0.0
    
    @property
    def sample_rate(self) -> int:
        """Get current sample rate."""
        return sd.query_devices(self.device)['default_samplerate'] if self.device is not None else sd.default.samplerate

    @property
    def device_name(self) -> str:
        """Get the name of the current audio device."""
        try:
            if self.device is not None:
                device_info = sd.query_devices(self.device)
                return device_info['name']
            else:
                # Using default device
                default_device = sd.default.device[1]  # [input, output]
                if default_device is not None:
                    device_info = sd.query_devices(default_device)
                    return f"{device_info['name']} (default)"
                return "Default Device"
        except Exception:
            return "Unknown Device"

    @staticmethod
    def list_output_devices():
        """
        List all available low-latency audio output devices.

        On Windows: ASIO and WASAPI devices
        On macOS: Core Audio devices
        On Linux: ALSA and JACK devices

        Returns:
            Tuple of (devices, api_names) where:
            - devices: List of tuples (device_id, device_name, host_api_name, device_info)
            - api_names: String describing the platform APIs (e.g., "ASIO/WASAPI")
        """
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        low_latency_apis, api_names = AudioDevice._get_platform_apis()
        available_devices = []

        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                hostapi = hostapis[device['hostapi']]
                hostapi_name = hostapi['name']

                if any(api in hostapi_name for api in low_latency_apis):
                    available_devices.append((i, device['name'], hostapi_name, device))

        return available_devices, api_names

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
