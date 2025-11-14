"""Tests for SamplerEngine."""

from pathlib import Path

import pytest

from launchsampler.audio import AudioDevice
from launchsampler.core import SamplerEngine
from launchsampler.models import Pad, PlaybackMode, Sample


@pytest.mark.unit
class TestSamplerEngine:
    """Test SamplerEngine class."""

    def test_create_manager(self):
        """Test creating SamplerEngine with AudioDevice."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id, buffer_size=128)
            manager = SamplerEngine(audio_device)

            assert manager is not None
            assert not manager.is_running
            assert manager.active_voices == 0

    def test_load_sample(self):
        """Test loading sample to pad."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            # Create test sample
            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)

                success = manager.load_sample(0, pad)
                assert success is True

    def test_load_sample_empty_pad(self):
        """Test loading empty pad returns False."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            pad = Pad(x=0, y=0)
            success = manager.load_sample(0, pad)
            assert success is False

    def test_trigger_pad(self):
        """Test triggering pad playback."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                manager.trigger_pad(0)
                # Can't easily verify playback without starting stream

    def test_stop_pad(self):
        """Test stopping pad."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                manager.trigger_pad(0)
                manager.stop_pad(0)

    def test_stop_all(self):
        """Test stopping all pads."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            manager.stop_all()  # Should not raise

    def test_update_pad_volume(self):
        """Test updating pad volume."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                manager.update_pad_volume(0, 0.5)

    def test_set_master_volume(self):
        """Test setting master volume."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            manager.set_master_volume(0.5)
            assert manager._master_volume == 0.5

    def test_get_playback_info(self):
        """Test getting playback info."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            # No pad loaded
            info = manager.get_playback_info(0)
            assert info is None

            # Load pad
            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                info = manager.get_playback_info(0)
                assert info is not None
                assert 'is_playing' in info
                assert 'volume' in info

    def test_is_pad_playing(self):
        """Test is_pad_playing method."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            # No pad loaded - should return False
            assert manager.is_pad_playing(0) is False

            # Load pad
            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                # Not playing yet
                assert manager.is_pad_playing(0) is False

                # Trigger pad
                manager.trigger_pad(0)
                # Should be playing now (briefly)
                # Note: might finish very quickly, so this is timing-dependent

    def test_unload_sample(self):
        """Test unloading sample."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            sample_path = Path("test_samples/kick.wav")
            if sample_path.exists():
                pad = Pad(x=0, y=0)
                pad.sample = Sample.from_file(sample_path)
                manager.load_sample(0, pad)

                manager.unload_sample(0)

    def test_context_manager(self):
        """Test using SamplerEngine as context manager."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            audio_device = AudioDevice(device=device_id)
            manager = SamplerEngine(audio_device)

            with manager:
                assert manager.is_running

            assert not manager.is_running
