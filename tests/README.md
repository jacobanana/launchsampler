# Tests

Unit tests for the Launchpad Sampler project using pytest.

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py

# Run specific test class
pytest tests/test_models.py::TestColor

# Run specific test
pytest tests/test_models.py::TestColor::test_create_color

# Run tests with specific marker
pytest -m unit
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_models.py           # Pydantic model tests (59 tests)
├── test_audio_data.py       # Audio dataclass tests (16 tests)
└── test_audio_manager.py    # Audio manager tests (16 tests)
```

## Test Organization

### Unit Tests (`@pytest.mark.unit`)

All current tests are unit tests that:
- Test individual components in isolation
- Do NOT test external libraries (Pydantic, sounddevice, NumPy)
- Focus on our business logic and integration between components
- Run quickly (< 1 second total)

### Test Coverage

#### Models (`test_models.py`)
- ✓ Color creation, validation, presets
- ✓ Sample file operations
- ✓ Pad assignment, clearing, validation
- ✓ Launchpad grid operations, MIDI conversion
- ✓ Set save/load
- ✓ AppConfig persistence

#### Audio Data (`test_audio_data.py`)
- ✓ AudioData mono/stereo creation
- ✓ Duration calculation, normalization
- ✓ Channel conversion
- ✓ PlaybackState lifecycle (start, stop, reset)
- ✓ Position advancement
- ✓ Loop mode behavior
- ✓ Frame extraction with volume

#### Audio Manager (`test_audio_manager.py`)
- ✓ SampleLoader file loading
- ✓ AudioMixer mixing, clipping
- ✓ AudioManager pad loading
- ✓ Playback control (trigger, stop)
- ✓ Volume control
- ✓ Device management

## Fixtures

Defined in `conftest.py`:

- `temp_dir` - Temporary directory for file operations
- `sample_audio_file` - Test WAV file (440 Hz sine wave)
- `sample_audio_array` - NumPy audio array
- `sample_model` - Sample Pydantic model
- `pad_empty` - Empty Pad instance
- `pad_with_sample` - Pad with sample assigned

## Test Principles

1. **Unit tests only** - No integration tests yet
2. **No library testing** - Trust Pydantic, sounddevice, NumPy
3. **Test our code** - Focus on business logic
4. **Fast execution** - All tests run in < 1 second
5. **Isolated** - Tests don't depend on each other
6. **Deterministic** - Same results every time

## What We DON'T Test

❌ Pydantic validation internals
❌ sounddevice audio playback
❌ NumPy array operations
❌ File I/O from soundfile
❌ Operating system features

We trust these libraries work correctly.

## What We DO Test

✅ Our models' business logic
✅ Custom validation logic
✅ Coordinate/MIDI note conversion
✅ Playback state management
✅ Audio mixing logic
✅ Manager coordination

## Adding New Tests

1. Add test function to appropriate file
2. Use existing fixtures when possible
3. Mark as `@pytest.mark.unit`
4. Follow naming: `test_<what_it_tests>`
5. Keep it focused - one thing per test
6. Don't test library internals

Example:

```python
@pytest.mark.unit
def test_new_feature(pad_empty):
    """Test description of what this tests."""
    # Arrange
    pad_empty.some_property = "value"

    # Act
    result = pad_empty.do_something()

    # Assert
    assert result == expected_value
```

## Future Test Types

Not implemented yet:

- Integration tests (`@pytest.mark.integration`)
- Audio playback tests (`@pytest.mark.audio`)
- MIDI hardware tests (`@pytest.mark.midi`)
- Performance tests (`@pytest.mark.performance`)
