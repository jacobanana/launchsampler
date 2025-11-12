"""Unit tests for audio manager components."""

import numpy as np
import pytest

from launchsampler.audio import AudioData, AudioManager, AudioMixer, PlaybackState, SampleLoader
from launchsampler.models import Pad, PlaybackMode, Sample


class TestSampleLoader:
    """Test SampleLoader."""

    @pytest.mark.unit
    def test_load_file(self, sample_audio_file):
        """Test loading an audio file."""
        loader = SampleLoader(target_sample_rate=44100)
        audio = loader.load(sample_audio_file)

        assert isinstance(audio, AudioData)
        assert audio.sample_rate == 44100
        assert audio.num_frames > 0

    @pytest.mark.unit
    def test_load_nonexistent_file(self, temp_dir):
        """Test that loading nonexistent file raises error."""
        loader = SampleLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(temp_dir / "nonexistent.wav")

    @pytest.mark.unit
    def test_get_info(self, sample_audio_file):
        """Test getting file info without loading."""
        info = SampleLoader.get_info(sample_audio_file)

        assert 'sample_rate' in info
        assert 'channels' in info
        assert 'duration' in info
        assert info['sample_rate'] == 44100


class TestAudioMixer:
    """Test AudioMixer."""

    @pytest.mark.unit
    def test_mix_empty_list(self):
        """Test mixing with no active sources."""
        mixer = AudioMixer(num_channels=2)
        output = mixer.mix([], num_frames=512)

        assert output.shape == (512, 2)
        assert np.all(output == 0)

    @pytest.mark.unit
    def test_mix_single_source(self, sample_audio_array):
        """Test mixing a single source."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, volume=1.0)
        state.start()

        mixer = AudioMixer(num_channels=2)
        output = mixer.mix([state], num_frames=512)

        assert output.shape == (512, 2)
        assert not np.all(output == 0)  # Should have audio

    @pytest.mark.unit
    def test_mix_multiple_sources(self, sample_audio_array):
        """Test mixing multiple sources."""
        audio1 = AudioData.from_array(sample_audio_array, sample_rate=44100)
        audio2 = AudioData.from_array(sample_audio_array * 0.5, sample_rate=44100)

        state1 = PlaybackState(audio_data=audio1, volume=0.5)
        state2 = PlaybackState(audio_data=audio2, volume=0.5)
        state1.start()
        state2.start()

        mixer = AudioMixer(num_channels=2)
        output = mixer.mix([state1, state2], num_frames=512)

        # Both should contribute to output
        assert output.shape == (512, 2)
        assert not np.all(output == 0)

    @pytest.mark.unit
    def test_apply_master_volume(self):
        """Test applying master volume."""
        buffer = np.ones((512, 2), dtype=np.float32)
        AudioMixer.apply_master_volume(buffer, volume=0.5)

        assert np.allclose(buffer, 0.5)

    @pytest.mark.unit
    def test_clip(self):
        """Test hard clipping."""
        buffer = np.array([[-2.0, 2.0]], dtype=np.float32)
        AudioMixer.clip(buffer)

        assert np.allclose(buffer, [[-1.0, 1.0]])

    @pytest.mark.unit
    def test_soft_clip(self):
        """Test soft clipping."""
        buffer = np.array([[2.0]], dtype=np.float32)
        AudioMixer.soft_clip(buffer)

        # tanh(2) should be less than 1 but greater than 0.9
        assert 0.9 < buffer[0, 0] < 1.0


class TestAudioManager:
    """Test AudioManager (without starting audio stream)."""

    @pytest.mark.unit
    def test_create_manager(self):
        """Test creating audio manager."""
        manager = AudioManager(sample_rate=44100, buffer_size=512)

        assert manager.sample_rate == 44100
        assert manager.buffer_size == 512
        assert manager.is_running is False

    @pytest.mark.unit
    def test_load_sample(self, sample_audio_file, pad_with_sample):
        """Test loading a sample into a pad."""
        manager = AudioManager()
        success = manager.load_sample(0, pad_with_sample)

        assert success is True

    @pytest.mark.unit
    def test_load_sample_empty_pad(self, pad_empty):
        """Test that loading empty pad returns False."""
        manager = AudioManager()
        success = manager.load_sample(0, pad_empty)

        assert success is False

    @pytest.mark.unit
    def test_trigger_pad(self, sample_audio_file, pad_with_sample):
        """Test triggering a pad."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)
        manager.trigger_pad(0)

        # Should have 1 active voice
        assert manager.active_voices == 1

    @pytest.mark.unit
    def test_stop_pad(self, sample_audio_file, pad_with_sample):
        """Test stopping a pad."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)
        manager.trigger_pad(0)
        manager.stop_pad(0)

        assert manager.active_voices == 0

    @pytest.mark.unit
    def test_stop_all(self, sample_audio_file, pad_with_sample):
        """Test stopping all pads."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)
        manager.load_sample(1, pad_with_sample)

        manager.trigger_pad(0)
        manager.trigger_pad(1)
        assert manager.active_voices == 2

        manager.stop_all()
        assert manager.active_voices == 0

    @pytest.mark.unit
    def test_update_pad_volume(self, sample_audio_file, pad_with_sample):
        """Test updating pad volume."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)
        manager.update_pad_volume(0, 0.5)

        info = manager.get_playback_info(0)
        assert info['volume'] == 0.5

    @pytest.mark.unit
    def test_set_master_volume(self):
        """Test setting master volume."""
        manager = AudioManager()
        manager.set_master_volume(0.7)

        assert manager._master_volume == 0.7

    @pytest.mark.unit
    def test_get_playback_info(self, sample_audio_file, pad_with_sample):
        """Test getting playback info."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)

        info = manager.get_playback_info(0)

        assert 'is_playing' in info
        assert 'progress' in info
        assert 'volume' in info
        assert info['mode'] == 'one_shot'

    @pytest.mark.unit
    def test_unload_sample(self, sample_audio_file, pad_with_sample):
        """Test unloading a sample."""
        manager = AudioManager()
        manager.load_sample(0, pad_with_sample)
        manager.unload_sample(0)

        info = manager.get_playback_info(0)
        assert info is not None  # State exists
        # But audio_data should be None (can't test directly, private)

    @pytest.mark.unit
    def test_list_devices(self):
        """Test listing audio devices."""
        devices = AudioManager.list_devices()
        # sounddevice returns a DeviceList object (not a list)
        assert len(devices) > 0

    @pytest.mark.unit
    def test_get_default_device(self):
        """Test getting default device."""
        device = AudioManager.get_default_device()
        assert isinstance(device, int)

    @pytest.mark.unit
    def test_device_validation_invalid_api(self):
        """Test that non-low-latency devices are rejected."""
        import sounddevice as sd

        # Get platform-specific low-latency APIs
        low_latency_apis, _ = AudioManager._get_platform_apis()

        # Find a device that doesn't use low-latency API
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        invalid_device = None
        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                hostapi = hostapis[device['hostapi']]
                if not any(api in hostapi['name'] for api in low_latency_apis):
                    invalid_device = i
                    break

        # If we found an invalid device, test that it's rejected
        if invalid_device is not None:
            with pytest.raises(ValueError, match="devices are supported for low-latency playback"):
                AudioManager(device=invalid_device)

    @pytest.mark.unit
    def test_device_validation_invalid_id(self):
        """Test that invalid device IDs are rejected."""
        with pytest.raises(ValueError, match="Invalid device ID"):
            AudioManager(device=999999)

    @pytest.mark.unit
    def test_get_platform_apis(self):
        """Test that platform APIs are correctly identified."""
        import sys

        apis, api_names = AudioManager._get_platform_apis()

        # Check return types
        assert isinstance(apis, list)
        assert isinstance(api_names, str)
        assert len(apis) > 0
        assert len(api_names) > 0

        # Check platform-specific values
        if sys.platform == 'win32':
            assert 'ASIO' in apis
            assert 'WASAPI' in apis
            assert 'ASIO/WASAPI' == api_names
        elif sys.platform == 'darwin':
            assert 'Core Audio' in apis
            assert 'Core Audio' == api_names
        else:
            assert 'ALSA' in apis
            assert 'JACK' in apis
            assert 'ALSA/JACK' == api_names

    @pytest.mark.unit
    def test_list_output_devices_returns_tuple(self):
        """Test that list_output_devices returns devices and API names."""
        devices, api_names = AudioManager.list_output_devices()

        # Check return types
        assert isinstance(devices, list)
        assert isinstance(api_names, str)

        # Check that API names are present
        assert len(api_names) > 0

        # If devices found, check structure
        if devices:
            for device_id, device_name, host_api, device_info in devices:
                assert isinstance(device_id, int)
                assert isinstance(device_name, str)
                assert isinstance(host_api, str)
                assert isinstance(device_info, dict)

                # Verify device uses a low-latency API
                low_latency_apis, _ = AudioManager._get_platform_apis()
                assert any(api in host_api for api in low_latency_apis)

    @pytest.mark.unit
    def test_is_valid_device_behavior(self):
        """Test device validation behavior across platforms."""
        import sounddevice as sd

        # Get a valid low-latency device
        devices, _ = AudioManager.list_output_devices()

        if devices:
            valid_device_id = devices[0][0]

            # Should return valid for low-latency device
            is_valid, hostapi_name, device_name = AudioManager._is_valid_device(valid_device_id)
            assert is_valid is True
            assert isinstance(hostapi_name, str)
            assert isinstance(device_name, str)

            # Verify hostapi uses a low-latency API
            low_latency_apis, _ = AudioManager._get_platform_apis()
            assert any(api in hostapi_name for api in low_latency_apis)
