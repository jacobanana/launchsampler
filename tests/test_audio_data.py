"""Unit tests for audio data structures (dataclasses)."""

import numpy as np
import pytest

from launchsampler.audio import AudioData, PlaybackState
from launchsampler.models import PlaybackMode


class TestAudioData:
    """Test AudioData dataclass."""

    @pytest.mark.unit
    def test_create_from_mono_array(self, sample_audio_array):
        """Test creating AudioData from mono array."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)

        assert audio.sample_rate == 44100
        assert audio.num_channels == 1
        assert audio.num_frames == len(sample_audio_array)
        assert audio.data.dtype == np.float32

    @pytest.mark.unit
    def test_create_from_stereo_array(self):
        """Test creating AudioData from stereo array."""
        stereo_data = np.random.randn(1000, 2).astype(np.float32)
        audio = AudioData.from_array(stereo_data, sample_rate=44100)

        assert audio.num_channels == 2
        assert audio.num_frames == 1000

    @pytest.mark.unit
    def test_duration_property(self):
        """Test duration calculation."""
        data = np.zeros(44100, dtype=np.float32)  # 1 second
        audio = AudioData.from_array(data, sample_rate=44100)

        assert audio.duration == pytest.approx(1.0, rel=1e-3)

    @pytest.mark.unit
    def test_get_mono_from_mono(self, sample_audio_array):
        """Test get_mono on already mono audio."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        mono = audio.get_mono()

        assert np.array_equal(mono, audio.data)

    @pytest.mark.unit
    def test_get_mono_from_stereo(self):
        """Test converting stereo to mono."""
        left = np.ones(100, dtype=np.float32)
        right = np.ones(100, dtype=np.float32) * 0.5
        stereo = np.column_stack([left, right])

        audio = AudioData.from_array(stereo, sample_rate=44100)
        mono = audio.get_mono()

        # Should be average of channels
        expected = (left + right) / 2
        assert np.allclose(mono, expected)

    @pytest.mark.unit
    def test_normalize(self):
        """Test audio normalization."""
        data = np.ones(100, dtype=np.float32) * 0.5
        audio = AudioData.from_array(data, sample_rate=44100)

        audio.normalize(target_level=0.95)

        assert np.abs(audio.data).max() == pytest.approx(0.95, rel=1e-3)

    @pytest.mark.unit
    def test_normalize_with_zero_peak(self):
        """Test normalization doesn't crash with silent audio."""
        data = np.zeros(100, dtype=np.float32)
        audio = AudioData.from_array(data, sample_rate=44100)

        # Should not crash or modify data
        audio.normalize(target_level=0.95)

        assert np.all(audio.data == 0)

    @pytest.mark.unit
    def test_from_array_with_invalid_dimensions(self):
        """Test from_array rejects invalid array dimensions."""
        # 3D array should fail
        data_3d = np.ones((10, 10, 10), dtype=np.float32)

        with pytest.raises(ValueError, match="must be 1D or 2D"):
            AudioData.from_array(data_3d, sample_rate=44100)

    @pytest.mark.unit
    def test_from_array_dtype_conversion(self):
        """Test from_array converts non-float32 to float32."""
        # Create int16 data
        data = np.ones(100, dtype=np.int16)
        audio = AudioData.from_array(data, sample_rate=44100)

        assert audio.data.dtype == np.float32

    @pytest.mark.unit
    def test_get_info(self):
        """Test get_info returns comprehensive metadata."""
        data = np.zeros(44100, dtype=np.float32)  # 1 second
        audio = AudioData.from_array(data, sample_rate=44100)
        audio.format = "WAV"
        audio.subtype = "PCM_16"

        info = audio.get_info()

        assert info["duration"] == pytest.approx(1.0, rel=1e-3)
        assert info["sample_rate"] == 44100
        assert info["num_channels"] == 1
        assert info["num_frames"] == 44100
        assert "size_bytes" in info
        assert "size_str" in info
        assert info["format"] == "WAV"
        assert info["subtype"] == "PCM_16"

    @pytest.mark.unit
    def test_get_info_without_format(self):
        """Test get_info works without format/subtype."""
        data = np.zeros(100, dtype=np.float32)
        audio = AudioData.from_array(data, sample_rate=44100)

        info = audio.get_info()

        assert "format" not in info
        assert "subtype" not in info

    @pytest.mark.unit
    def test_shape_property(self):
        """Test shape property returns audio data shape."""
        mono_data = np.zeros(100, dtype=np.float32)
        mono_audio = AudioData.from_array(mono_data, sample_rate=44100)
        assert mono_audio.shape == (100,)

        stereo_data = np.zeros((100, 2), dtype=np.float32)
        stereo_audio = AudioData.from_array(stereo_data, sample_rate=44100)
        assert stereo_audio.shape == (100, 2)


class TestPlaybackState:
    """Test PlaybackState dataclass."""

    @pytest.mark.unit
    def test_initial_state(self, sample_audio_array):
        """Test initial playback state."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        assert state.is_playing is False
        assert state.position == 0.0
        assert state.volume == 1.0

    @pytest.mark.unit
    def test_start_playback(self, sample_audio_array):
        """Test starting playback."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.start()

        assert state.is_playing is True
        assert state.position == 0.0

    @pytest.mark.unit
    def test_stop_playback(self, sample_audio_array):
        """Test stopping playback."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.start()
        state.stop()

        assert state.is_playing is False

    @pytest.mark.unit
    def test_advance_position(self, sample_audio_array):
        """Test advancing playback position."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.ONE_SHOT)

        state.start()
        state.advance(100)

        assert state.position == 100

    @pytest.mark.unit
    def test_advance_past_end_oneshot(self, sample_audio_array):
        """Test that ONE_SHOT mode stops at end."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.ONE_SHOT)

        state.start()
        state.advance(len(sample_audio_array) + 100)

        assert state.is_playing is False

    @pytest.mark.unit
    def test_advance_loop_mode(self, sample_audio_array):
        """Test that LOOP mode wraps position."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.LOOP)

        state.start()
        initial_length = len(sample_audio_array)
        state.advance(initial_length + 50)

        # Should have looped
        assert state.is_playing is True
        assert state.position == 50

    @pytest.mark.unit
    def test_seamless_loop(self, sample_audio_array):
        """Test seamless looping at buffer boundary."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.LOOP)

        state.start()
        # Position near end of buffer
        buffer_size = len(sample_audio_array)
        state.position = buffer_size - 10

        # Request more frames than available before loop
        frames = state.get_frames(20)

        # Should get exactly 20 frames (10 from end + 10 from beginning)
        assert frames is not None
        assert len(frames) == 20

        # First 10 should match end of buffer
        np.testing.assert_array_almost_equal(frames[:10], sample_audio_array[-10:])

        # Last 10 should match beginning of buffer
        np.testing.assert_array_almost_equal(frames[10:], sample_audio_array[:10])

    @pytest.mark.unit
    def test_get_frames(self, sample_audio_array):
        """Test getting audio frames."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, volume=0.5)

        state.start()
        frames = state.get_frames(100)

        assert frames is not None
        assert len(frames) == 100
        # Volume should be applied
        assert np.abs(frames).max() <= 0.5

    @pytest.mark.unit
    def test_get_frames_not_playing(self, sample_audio_array):
        """Test that get_frames returns None when not playing."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        frames = state.get_frames(100)

        assert frames is None

    @pytest.mark.unit
    def test_progress_property(self, sample_audio_array):
        """Test playback progress calculation."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.start()
        state.position = len(sample_audio_array) / 2

        assert state.progress == pytest.approx(0.5, rel=1e-2)

    @pytest.mark.unit
    def test_reset(self, sample_audio_array):
        """Test resetting playback state."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.start()
        state.advance(100)
        state.reset()

        assert state.is_playing is False
        assert state.position == 0.0

    @pytest.mark.unit
    def test_start_without_audio_data(self):
        """Test that starting without audio data raises error."""
        state = PlaybackState()

        with pytest.raises(ValueError, match="Cannot start playback without audio data"):
            state.start()

    @pytest.mark.unit
    def test_stop_with_loop_toggle_mode(self, sample_audio_array):
        """Test stopping in LOOP_TOGGLE mode resets toggle state."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.LOOP_TOGGLE)

        state.start()
        state._loop_toggle_state = True  # Simulate toggle state
        state.stop()

        assert state.is_playing is False
        assert state._loop_toggle_state is False

    @pytest.mark.unit
    def test_time_elapsed(self, sample_audio_array):
        """Test time_elapsed property."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.position = 22050  # Half a second at 44100 Hz

        assert state.time_elapsed == pytest.approx(0.5, rel=1e-3)

    @pytest.mark.unit
    def test_time_elapsed_without_audio_data(self):
        """Test time_elapsed returns 0 without audio data."""
        state = PlaybackState()

        assert state.time_elapsed == 0.0

    @pytest.mark.unit
    def test_time_remaining(self, sample_audio_array):
        """Test time_remaining property."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio)

        state.position = len(sample_audio_array) / 2

        expected_remaining = (len(sample_audio_array) / 2) / 44100
        assert state.time_remaining == pytest.approx(expected_remaining, rel=1e-3)

    @pytest.mark.unit
    def test_time_remaining_without_audio_data(self):
        """Test time_remaining returns 0 without audio data."""
        state = PlaybackState()

        assert state.time_remaining == 0.0

    @pytest.mark.unit
    def test_progress_without_audio_data(self):
        """Test progress returns 0 without audio data."""
        state = PlaybackState()

        assert state.progress == 0.0

    @pytest.mark.unit
    def test_get_frames_with_stereo_truncate(self):
        """Test get_frames with stereo audio truncating at end (ONE_SHOT mode)."""
        # Create stereo audio
        stereo_data = np.random.randn(100, 2).astype(np.float32)
        audio = AudioData.from_array(stereo_data, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.ONE_SHOT)

        state.start()
        state.position = 90  # Near end

        # Request more frames than available
        frames = state.get_frames(20)

        # Should get truncated to 10 frames
        assert frames is not None
        assert len(frames) == 10

    @pytest.mark.unit
    def test_get_frames_with_stereo_loop(self):
        """Test get_frames with stereo audio wrapping in LOOP mode."""
        # Create stereo audio
        stereo_data = np.random.randn(100, 2).astype(np.float32)
        audio = AudioData.from_array(stereo_data, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.LOOP)

        state.start()
        state.position = 95  # Near end

        # Request more frames than available before loop
        frames = state.get_frames(10)

        # Should get 10 frames (5 from end + 5 from beginning)
        assert frames is not None
        assert len(frames) == 10
        assert frames.shape == (10, 2)  # Stereo

    @pytest.mark.unit
    def test_get_frames_past_end(self, sample_audio_array):
        """Test get_frames returns None when position past end."""
        audio = AudioData.from_array(sample_audio_array, sample_rate=44100)
        state = PlaybackState(audio_data=audio, mode=PlaybackMode.ONE_SHOT)

        state.is_playing = True
        state.position = len(sample_audio_array) + 100  # Past end

        frames = state.get_frames(10)

        assert frames is None

    @pytest.mark.unit
    def test_get_frames_with_stereo_normal(self):
        """Test get_frames with stereo audio in normal case (no wrapping)."""
        # Create stereo audio with controlled values
        stereo_data = np.ones((100, 2), dtype=np.float32)
        audio = AudioData.from_array(stereo_data, sample_rate=44100)
        state = PlaybackState(audio_data=audio, volume=0.5)

        state.start()
        frames = state.get_frames(10)

        assert frames is not None
        assert frames.shape == (10, 2)  # Stereo
        # Volume should be applied (1.0 * 0.5 = 0.5)
        assert np.allclose(frames, 0.5)
