# Launchpad Sampler

[![CI](https://github.com/jacobanana/launchsampler/actions/workflows/ci.yml/badge.svg)](https://github.com/jacobanana/launchsampler/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://jacobanana.github.io/launchsampler/badges/coverage.json)](https://github.com/jacobanana/launchsampler/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12%20|%203.13-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue)](https://jacobanana.github.io/launchsampler/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A lean, type-safe audio sampler for the Novation Launchpad built with Python.

## Overview

Launchpad Sampler provides low-latency audio playback for 64 pads (8×8 grid) with real-time mixing, multiple playback modes, and JSON-based configuration. Built using sounddevice for audio I/O and Pydantic for type-safe data models.

## Quick Start

```bash
# Install
uv sync

# Run tests
uv run pytest

# Run application
uv run launchsampler
```

## Architecture

### Core Layers

**1. Models** (Pydantic) - Serializable configuration
- Color, Sample, Pad, Launchpad, Set, AppConfig
- JSON persistence, type-safe validation

**2. Audio** (NumPy + sounddevice) - Real-time playback
- AudioData, PlaybackState (dataclasses for performance)
- SampleLoader, AudioMixer, AudioManager
- Low-latency mixing, 64+ voices

**3. MIDI** (mido) - Generic MIDI I/O
- MidiInputManager, MidiOutputManager, MidiManager
- Hot-plug support, callback-based
- Device-agnostic with optional port selection

**4. Launchpad** - Device-specific protocol
- LaunchpadDevice (patterns, parsing, port selection)
- LaunchpadController (high-level API)
- Composes generic MIDI with Launchpad protocol

**5. CLI** (Click) - User interface
- Commands: `run`, `list audio`, `list midi`
- ASIO/WASAPI device filtering

### Design Rationale

- **Pydantic**: Validation, serialization (metadata only)
- **Dataclasses**: 500× faster (hot audio paths)
- **Separation**: Generic MIDI reusable for other controllers
- **Composition**: Device logic in protocol, not managers

## Features

- **8×8 Grid**: 64 pads with MIDI note mapping
- **Playback Modes**: One-shot, loop, hold
- **Real-time Mixing**: 64+ simultaneous voices
- **Low Latency**: 11.6ms @ 512 frames (configurable)
- **Audio Formats**: WAV, FLAC, OGG via soundfile
- **Caching**: Loaded samples stay in memory
- **Thread-safe**: All operations safe from any thread
- **Type-safe**: Full Pydantic validation
- **Persistence**: Save/load configurations as JSON

## Technology Stack

```toml
[dependencies]
numpy = ">=2.3.4"        # Audio buffers
pydantic = ">=2.12.4"    # Data models
sounddevice = ">=0.5.3"  # Audio I/O
soundfile = ">=0.13.0"   # File loading
```

**Testing:** pytest

## Design Principles

1. **Lean**: No bloat, essential features only
2. **Performance**: Dataclasses for hot paths, NumPy for arrays
3. **Type-safe**: Pydantic validation, full type hints
4. **Real-time safe**: Minimal GC pressure, lock-free audio callback
5. **Serializable**: All configuration stored as JSON
6. **Testable**: Unit tests only, trust libraries

## File Structure

```
src/launchsampler/
├── models/          # Pydantic models (config, serialization)
├── audio/           # Audio engine (playback, mixing)
├── midi/            # Generic MIDI I/O (hot-plug, managers)
├── launchpad/       # Launchpad-specific (device, controller)
└── cli/             # Click commands (run, list)

tests/               # Unit tests
```

## Testing

```bash
# All tests
uv run pytest

# Verbose
uv run pytest -v

# Specific
uv run pytest tests/test_models.py

# With warnings
uv run pytest -W default
```

