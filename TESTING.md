# Testing Guide

## Overview

The project uses **pytest** for testing with a focus on lean, essential unit tests.

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py

# Run only unit tests
pytest -m unit

# Run with coverage (if installed)
pytest --cov=src/launchsampler
```

## Test Statistics

- **Total Tests:** 59
- **Test Files:** 3
- **Execution Time:** < 1 second
- **Pass Rate:** 100%

### Breakdown

```
test_models.py          - 28 tests (Models)
test_audio_data.py      - 16 tests (Audio dataclasses)
test_audio_manager.py   - 15 tests (Audio engine)
```

## Test Organization

```
tests/
├── conftest.py              # Shared pytest fixtures
├── test_models.py           # Pydantic model tests
├── test_audio_data.py       # AudioData & PlaybackState tests
├── test_audio_manager.py    # Audio engine component tests
└── README.md                # Detailed test documentation
```

## Test Philosophy

### What We Test ✅

- **Our business logic** - Custom model methods, validation
- **Coordinate conversions** - MIDI note ↔ (x, y) mapping
- **State management** - PlaybackState lifecycle
- **Audio mixing** - Our mixing algorithm
- **Component integration** - How our classes work together

### What We DON'T Test ❌

- **Library internals** - We trust Pydantic, sounddevice, NumPy
- **External I/O** - File system, audio hardware
- **Library validation** - Pydantic's validation logic
- **Third-party functions** - NumPy operations

### Why This Approach?

1. **Fast** - Tests run in < 1 second
2. **Focused** - Only test our code
3. **Maintainable** - Less tests to update when dependencies change
4. **Reliable** - No flaky tests from external dependencies

## Key Fixtures

Defined in `conftest.py`:

```python
temp_dir            # Temporary directory
sample_audio_file   # Test WAV file (440 Hz tone)
sample_audio_array  # NumPy audio array
sample_model        # Sample Pydantic model
pad_empty           # Empty Pad
pad_with_sample     # Pad with sample assigned
```

## Test Coverage by Component

### Models (28 tests)

#### Color (4 tests)
- Creation with RGB values
- Validation (0-127 range)
- Preset colors (red, green, blue, etc.)
- RGB tuple conversion

#### Sample (2 tests)
- Creation from file path
- File existence checking

#### Pad (5 tests)
- Empty pad creation
- Coordinate validation (0-7)
- Sample assignment
- Position property
- Clearing pad

#### Launchpad (6 tests)
- Empty grid creation (64 pads)
- Get pad by coordinates
- Invalid coordinate handling
- MIDI note → (x, y) conversion
- (x, y) → MIDI note conversion
- Assigned pads filtering

#### Set (2 tests)
- Empty set creation
- Save/load to JSON

#### AppConfig (3 tests)
- Default configuration
- Load or create default
- Save/load configuration

### Audio Data (16 tests)

#### AudioData (6 tests)
- Mono array creation
- Stereo array creation
- Duration calculation
- Mono extraction from mono
- Stereo to mono conversion
- Audio normalization

#### PlaybackState (10 tests)
- Initial state
- Start playback
- Stop playback
- Position advancement
- ONE_SHOT mode (stops at end)
- LOOP mode (wraps position)
- Frame extraction
- Not playing returns None
- Progress calculation
- Reset state

### Audio Manager (15 tests)

#### SampleLoader (3 tests)
- Load audio file
- Nonexistent file error
- Get file info

#### AudioMixer (6 tests)
- Mix empty list (silence)
- Mix single source
- Mix multiple sources
- Apply master volume
- Hard clipping
- Soft clipping (tanh)

#### AudioManager (6 tests)
- Manager creation
- Load sample into pad
- Empty pad loading fails
- Trigger pad playback
- Stop pad
- Stop all pads
- Update pad volume
- Set master volume
- Get playback info
- Unload sample
- List audio devices
- Get default device

## Running Specific Tests

```bash
# Test only Color model
pytest tests/test_models.py::TestColor -v

# Test only PlaybackState
pytest tests/test_audio_data.py::TestPlaybackState -v

# Test only AudioMixer
pytest tests/test_audio_manager.py::TestAudioMixer -v

# Test a specific function
pytest tests/test_models.py::TestColor::test_create_color -v
```

## Continuous Integration

Add to CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Run tests
  run: |
    pip install pytest
    pytest tests/ -v
```

## Future Test Types

Currently all tests are unit tests. Future additions:

- **Integration tests** - Test components working together
- **Audio tests** - Tests that produce actual audio output
- **MIDI tests** - Tests with hardware (when available)
- **Performance tests** - Benchmark critical paths

## Test Markers

Configured in `pytest.ini`:

```ini
@pytest.mark.unit         # Unit tests (all current tests)
@pytest.mark.integration  # Integration tests (future)
@pytest.mark.audio        # May produce audio (future)
```

## Adding New Tests

1. Choose appropriate test file
2. Use existing fixtures when possible
3. Follow naming convention: `test_<what_it_tests>`
4. Keep tests focused (one thing per test)
5. Add `@pytest.mark.unit` decorator
6. Don't test library internals

Example:

```python
class TestNewFeature:
    """Test new feature."""

    @pytest.mark.unit
    def test_feature_behavior(self, fixture_name):
        """Test specific behavior."""
        # Arrange
        obj = create_object()

        # Act
        result = obj.do_something()

        # Assert
        assert result == expected
```

## Troubleshooting

### Tests not found
```bash
# Make sure you're in the project root
cd /path/to/launchsampler
pytest tests/
```

### Import errors
```bash
# Install package in development mode
pip install -e .
```

### Slow tests
```bash
# Our tests should run in < 1 second
# If slower, profile with:
pytest --durations=10
```

## Summary

- ✅ 59 unit tests covering all core functionality
- ✅ Fast execution (< 1 second)
- ✅ 100% pass rate
- ✅ Focused on our code, not libraries
- ✅ Well-organized with clear fixtures
- ✅ Easy to extend

The testing suite is lean, fast, and covers what matters!
