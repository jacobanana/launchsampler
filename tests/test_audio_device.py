"""Tests for AudioDevice."""

import pytest

from launchsampler.audio import AudioDevice


@pytest.mark.unit
class TestAudioDevice:
    """Test AudioDevice class."""

    def test_get_platform_apis(self):
        """Test that platform APIs are correctly identified."""
        import sys

        apis, api_names = AudioDevice._get_platform_apis()

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
            assert 'ASIO' in apis
            assert 'JACK' in apis
            assert 'ALSA/JACK' == api_names

    def test_list_output_devices_returns_tuple(self):
        """Test that list_output_devices returns devices and API names."""
        devices, api_names = AudioDevice.list_output_devices()

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
                low_latency_apis, _ = AudioDevice._get_platform_apis()
                assert any(api in host_api for api in low_latency_apis)

    def test_is_valid_device_behavior(self):
        """Test device validation behavior across platforms."""
        # Get a valid low-latency device
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            valid_device_id = devices[0][0]

            # Should return valid for low-latency device
            is_valid, hostapi_name, device_name = AudioDevice._is_valid_device(valid_device_id)
            assert is_valid is True
            assert isinstance(hostapi_name, str)
            assert isinstance(device_name, str)

            # Verify hostapi uses a low-latency API
            low_latency_apis, _ = AudioDevice._get_platform_apis()
            assert any(api in hostapi_name for api in low_latency_apis)

    def test_device_validation_invalid_api(self):
        """Test that non-low-latency devices fall back to default device."""
        import sounddevice as sd

        # Get platform-specific low-latency APIs
        low_latency_apis, _ = AudioDevice._get_platform_apis()

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

        # If we found an invalid device, test that it falls back to default
        if invalid_device is not None:
            device = AudioDevice(device=invalid_device)

            # Should fall back to default device (None)
            assert device.device is None

    def test_device_validation_invalid_id(self):
        """Test that invalid device IDs fall back to default device."""
        # Invalid device ID should fall back to default device with warning
        device = AudioDevice(device=999999)

        # Should fall back to default device (None)
        assert device.device is None

    def test_device_validation_invalid_id_fallback_with_unavailable_device(self):
        """Test that unavailable device IDs (e.g., unplugged hardware) fall back to default."""
        # Use a device ID that's technically valid format but likely doesn't exist
        device = AudioDevice(device=99)

        # Should fall back to default device (None)
        assert device.device is None

    def test_get_default_device(self):
        """Test getting default device."""
        device = AudioDevice.get_default_device()
        assert isinstance(device, int)

    def test_create_device(self):
        """Test creating AudioDevice instance."""
        # Get a valid device
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            device = AudioDevice(
                device=device_id,
                buffer_size=128
            )

            assert device.buffer_size == 128
            assert device.device == device_id
            assert not device.is_running

    def test_set_callback(self):
        """Test setting audio callback."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            device = AudioDevice(device=device_id)

            callback_called = False

            def test_callback(outdata, frames):
                nonlocal callback_called
                callback_called = True

            device.set_callback(test_callback)
            assert device._callback is not None

    def test_start_without_callback_raises(self):
        """Test that starting without callback raises error."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            device = AudioDevice(device=device_id)

            with pytest.raises(RuntimeError, match="No audio callback set"):
                device.start()

    def test_device_name(self):
        """Test getting device name."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            device = AudioDevice(device=device_id)

            # Should return a non-empty string
            name = device.device_name
            assert isinstance(name, str)
            assert len(name) > 0
            assert name != "Unknown Device"

        # Test with default device (None)
        default_device = AudioDevice(device=None)
        name = default_device.device_name
        assert isinstance(name, str)
        assert len(name) > 0

    def test_context_manager(self):
        """Test using AudioDevice as context manager."""
        devices, _ = AudioDevice.list_output_devices()

        if devices:
            device_id = devices[0][0]
            device = AudioDevice(device=device_id)

            def dummy_callback(outdata, frames):
                outdata.fill(0)

            device.set_callback(dummy_callback)

            # Test context manager
            with device:
                assert device.is_running

            # Should be stopped after exit
            assert not device.is_running

    def test_device_in_use_error_message(self):
        """Test that device-in-use errors provide helpful message."""
        from unittest.mock import patch, MagicMock
        import sounddevice as sd

        # Mock sounddevice to raise an error with PaErrorCode -9996
        mock_stream = MagicMock()
        mock_stream.side_effect = Exception("Error opening OutputStream: Invalid device [PaErrorCode -9996]")

        with patch.object(sd, 'OutputStream', mock_stream):
            device = AudioDevice(device=None)
            device.set_callback(lambda outdata, frames: None)

            # Should raise RuntimeError with helpful message
            with pytest.raises(RuntimeError, match="Audio device is already in use"):
                device.start()
