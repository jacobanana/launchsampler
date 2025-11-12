"""Pytest fixtures for tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
import soundfile as sf

from launchsampler.models import Color, Pad, PlaybackMode, Sample


@pytest.fixture
def temp_dir():
    """Create a temporary directory that gets cleaned up."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_audio_file(temp_dir):
    """Create a simple test audio file."""
    sample_rate = 44100
    duration = 0.1  # 100ms
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    file_path = temp_dir / "test.wav"
    sf.write(str(file_path), audio_data, sample_rate)

    return file_path


@pytest.fixture
def sample_audio_array():
    """Generate sample audio data as NumPy array."""
    sample_rate = 44100
    duration = 0.1
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def sample_model(sample_audio_file):
    """Create a Sample model instance."""
    return Sample.from_file(sample_audio_file)


@pytest.fixture
def pad_empty():
    """Create an empty Pad."""
    return Pad.empty(x=0, y=0)


@pytest.fixture
def pad_with_sample(sample_model):
    """Create a Pad with a sample assigned."""
    pad = Pad(x=0, y=0)
    pad.sample = sample_model
    pad.color = Color(r=127, g=0, b=0)  # Red
    pad.mode = PlaybackMode.ONE_SHOT
    pad.volume = 0.8
    return pad
