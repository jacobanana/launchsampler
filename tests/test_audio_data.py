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
