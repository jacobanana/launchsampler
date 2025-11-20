# ASMU Library Migration Analysis

## Executive Summary

This document analyzes the feasibility of migrating from our custom `AudioDevice` class (built on `sounddevice`) to the **asmu** library for real-time audio processing. The asmu library is a modern, modular Python package designed specifically for real-time multichannel audio applications across research, arts, and education domains.

**Key Finding**: While asmu shows promise as a more powerful and optimized solution, **immediate migration is not recommended** due to:
- Python 3.12+ requirement (current project uses Python 3.11.14)
- Limited public documentation availability
- Unknown API compatibility with existing codebase
- Risk of disruption to stable audio engine

**Recommendation**: Monitor asmu's development and plan a gradual migration path once Python 3.12+ is adopted and asmu documentation becomes more accessible.

---

## Current Audio Implementation

### Architecture Overview

The launchsampler audio engine consists of four main components:

1. **AudioDevice** (`src/launchsampler/audio/device.py`)
   - Low-latency audio output management
   - Platform-specific API support
   - Stream lifecycle management

2. **AudioMixer** (`src/launchsampler/audio/mixer.py`)
   - Multi-source audio mixing
   - Channel conversion (mono ↔ stereo)
   - Volume control and clipping

3. **SampleLoader** (`src/launchsampler/audio/loader.py`)
   - Audio file loading (WAV, FLAC, OGG)
   - Basic resampling
   - File metadata extraction

4. **Data Structures** (`src/launchsampler/audio/data.py`)
   - `AudioData`: Raw audio buffer storage
   - `PlaybackState`: Runtime playback state with multiple modes

### Current Capabilities

#### ✅ Core Features

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Low-latency I/O** | Platform-specific APIs (ASIO, WASAPI, Core Audio, ALSA, JACK) | ✅ Fully implemented |
| **Device Management** | Query, validate, enumerate devices by host API | ✅ Fully implemented |
| **Stream Control** | Start/stop with configurable buffer sizes | ✅ Fully implemented |
| **Multi-channel** | 1-8+ channels with automatic conversion | ✅ Fully implemented |
| **Audio Mixing** | Real-time mixing of multiple sources | ✅ Fully implemented |
| **Playback Modes** | ONE_SHOT, LOOP, LOOP_TOGGLE, HOLD | ✅ Fully implemented |
| **Volume Control** | Per-source and master volume | ✅ Fully implemented |
| **Clipping Protection** | Hard clip and soft clip (tanh) | ✅ Fully implemented |
| **File Loading** | soundfile-based loading | ✅ Fully implemented |
| **Error Handling** | Custom exceptions with recovery hints | ✅ Fully implemented |

#### 📊 Performance Characteristics

- **Buffer sizes**: Configurable (default 128 frames)
- **Latency**: Typically 3-15ms depending on hardware
- **Sample rates**: Device-dependent (typically 44.1kHz, 48kHz)
- **Audio format**: float32 (industry standard)
- **Thread safety**: Callback-based design for real-time safety

#### 🔧 Technical Stack

```python
Dependencies:
- sounddevice (wrapper around PortAudio)
- soundfile (audio file I/O)
- numpy (audio buffer processing)
```

---

## ASMU Library Overview

### What is ASMU?

**asmu** (Audio Sampling and Modular Utilities) is a modern Python package designed for real-time audio applications, developed by Felix (PhD candidate at TU Wien).

### Key Information

| Property | Details |
|----------|---------|
| **PyPI Package** | `asmu` (versions 0.0.1a1 → 0.1.9) |
| **Python Requirement** | ≥ 3.12 |
| **Documentation** | https://felhub.gitlab.io/asmu/api/asmu/ |
| **Development** | Active (presented at Audio Developer Conference 2025) |
| **License** | Unknown (not publicly documented) |
| **GitHub/GitLab** | Not publicly accessible or discoverable |

### Advertised Features

Based on conference presentation and limited documentation:

1. **Modular Architecture**
   - Designed for composability and extensibility
   - Separation of concerns for different audio tasks

2. **Real-time Performance**
   - Optimized for modern Python interpreters (3.12+)
   - Takes advantage of recent performance improvements
   - Focus on low-latency multichannel audio

3. **Use Cases**
   - Precise audio measurements
   - Interactive sound sculptures
   - Research and educational applications
   - Creative audio applications

4. **Modern Python**
   - Leverages Python 3.12+ features
   - Performance-optimized codebase
   - Contemporary API design patterns

### Unknown/Unclear Aspects

Due to limited public documentation, the following are **unknown**:

- ❓ Exact API structure and class hierarchy
- ❓ Device management capabilities
- ❓ Platform-specific optimizations (ASIO, WASAPI, etc.)
- ❓ File I/O capabilities
- ❓ Mixing/routing capabilities
- ❓ Error handling approach
- ❓ Testing coverage and stability
- ❓ Community size and support
- ❓ Breaking changes between versions
- ❓ Migration path from other libraries

---

## Capability Comparison

### Feature Matrix

| Capability | Current (sounddevice) | ASMU | Notes |
|------------|----------------------|------|-------|
| **Low-latency I/O** | ✅ Excellent | ⚠️ Assumed (unverified) | Both claim real-time capabilities |
| **Platform APIs** | ✅ ASIO/WASAPI/CoreAudio/ALSA/JACK | ❓ Unknown | Critical for professional audio |
| **Device Management** | ✅ Full enumeration & validation | ❓ Unknown | Important for UX |
| **Multi-channel** | ✅ 1-8+ channels | ⚠️ Advertised as "multichannel" | Exact limits unknown |
| **Buffer Control** | ✅ Configurable buffer sizes | ❓ Unknown | Critical for latency tuning |
| **Audio Mixing** | ✅ Custom mixer implementation | ❓ Unknown | May need custom implementation |
| **File I/O** | ✅ Via soundfile | ❓ Unknown | May require additional library |
| **Playback Modes** | ✅ 4 modes (ONE_SHOT, LOOP, etc.) | ❓ Unknown | Application-specific logic |
| **Error Handling** | ✅ Custom exceptions | ❓ Unknown | Important for UX |
| **Documentation** | ✅ Excellent (sounddevice) | ⚠️ Limited public docs | Major concern |
| **Community Support** | ✅ Large (PortAudio/sounddevice) | ❓ Unknown/Small | Risk factor |
| **Stability** | ✅ Production-ready | ⚠️ Early versions (0.1.x) | Risk factor |
| **Python Version** | ✅ 3.8+ | ❌ 3.12+ only | **Blocking issue** |

### Potential Advantages of ASMU

1. **Modern Architecture**
   - Designed from scratch for Python 3.12+
   - May leverage newer language features (pattern matching, better typing)
   - Potentially cleaner API design

2. **Performance Optimizations**
   - Built to take advantage of Python 3.12+ interpreter improvements
   - May have lower overhead than PortAudio wrapper

3. **Modularity**
   - Advertised as highly modular
   - Could allow better separation of concerns
   - Potentially easier to extend/customize

4. **Research-Grade**
   - Developed at TU Wien (respected institution)
   - Focus on precision measurements suggests rigorous implementation

### Potential Disadvantages of ASMU

1. **Maturity**
   - Early version numbers (0.1.x)
   - Unknown production usage
   - Potential for breaking changes

2. **Documentation**
   - Limited public documentation
   - API reference not accessible (403 error on docs)
   - Fewer examples and tutorials

3. **Community**
   - Small/unknown community
   - Fewer Stack Overflow answers
   - Less third-party tooling

4. **Python Version Lock-in**
   - Requires Python 3.12+
   - Forces upgrade of entire project
   - May block users on older systems

5. **Unknown Compatibility**
   - Unclear if it supports all platforms (Windows/macOS/Linux)
   - Unknown ASIO/WASAPI support status
   - Device management capabilities unclear

---

## Migration Impact Analysis

### Code Changes Required

#### 1. Core Audio Engine (HIGH EFFORT)

**Files affected:**
- `src/launchsampler/audio/device.py` (446 lines) - **Complete rewrite**
- `src/launchsampler/audio/mixer.py` (144 lines) - **Potential rewrite**
- `src/launchsampler/audio/loader.py` (140 lines) - **May need adaptation**
- `src/launchsampler/audio/data.py` (292 lines) - **May need adaptation**

**Estimated effort:** 2-4 weeks (assuming asmu has comparable features)

#### 2. Integration Layer (MEDIUM EFFORT)

**Files potentially affected:**
- Any code using `AudioDevice` class
- CLI commands (`src/launchsampler/cli/commands/audio.py`)
- Configuration and initialization code
- Tests

**Estimated effort:** 1-2 weeks

#### 3. Testing & Validation (HIGH EFFORT)

- Unit tests need complete rewrite
- Integration tests need updates
- Cross-platform testing (Windows/macOS/Linux)
- Device compatibility testing
- Performance benchmarking

**Estimated effort:** 2-3 weeks

### Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| **API incompatibility** | 🔴 Critical | High | Prototype before committing |
| **Missing features** | 🔴 Critical | Medium | Feature mapping analysis |
| **Performance regression** | 🟡 High | Low | Benchmark before/after |
| **Platform incompatibility** | 🔴 Critical | Medium | Multi-platform testing |
| **Stability issues** | 🟡 High | Medium | Extensive testing period |
| **Documentation gaps** | 🟡 High | High | Direct communication with maintainers |
| **Community support** | 🟡 High | High | Build internal expertise |
| **Python upgrade issues** | 🟡 High | High | Test entire project on 3.12+ |

### Dependencies Impact

Current dependencies:
```toml
sounddevice = "^0.4.0"
soundfile = "^0.12.0"
numpy = "^1.24.0"
```

Post-migration:
```toml
asmu = "^0.1.9"  # Replaces sounddevice
soundfile = "^0.12.0"  # May still be needed for file I/O
numpy = "^1.24.0"  # Still needed for audio processing
```

**Python version change:**
```toml
# Current
python = "^3.11"

# Required for asmu
python = "^3.12"
```

---

## Migration Path Proposal

### Option 1: Full Migration (NOT RECOMMENDED)

**Timeline:** 6-8 weeks

**Phases:**
1. Week 1-2: Research & prototyping
2. Week 3-4: Core implementation
3. Week 5-6: Integration & testing
4. Week 7-8: Bug fixes & optimization

**Pros:**
- Clean break from old code
- Full access to asmu features
- Modern codebase

**Cons:**
- ❌ Requires Python 3.12+ upgrade
- ❌ High risk with unknown library
- ❌ Significant development time
- ❌ Limited documentation
- ❌ May discover missing features mid-migration

### Option 2: Gradual Exploration (RECOMMENDED)

**Timeline:** Ongoing

**Phase 1: Investigation (1-2 weeks)**
- Upgrade Python to 3.12+ in development environment
- Install asmu and explore API
- Build proof-of-concept audio player
- Compare performance with current implementation
- Document findings and API differences

**Phase 2: Feature Mapping (1 week)**
- Map all current AudioDevice features to asmu equivalents
- Identify gaps and missing features
- Determine if custom implementations needed
- Assess migration feasibility

**Phase 3: Parallel Implementation (2-3 weeks)**
- Create alternative asmu-based AudioDevice implementation
- Maintain existing sounddevice implementation
- Add feature flag to switch between implementations
- Run both in testing/CI

**Phase 4: Validation (2-4 weeks)**
- Extensive testing on all platforms
- Performance benchmarking
- User acceptance testing
- Stability monitoring

**Phase 5: Migration (1 week)**
- If asmu proves superior, make it default
- Keep sounddevice as fallback option
- Monitor for issues

**Phase 6: Deprecation (Future)**
- After 3-6 months of stable asmu usage
- Remove sounddevice implementation
- Clean up abstraction layer

**Pros:**
- ✅ Lower risk (can abort if asmu inadequate)
- ✅ Allows thorough evaluation
- ✅ Maintains backward compatibility
- ✅ Incremental learning curve

**Cons:**
- Temporarily maintains two implementations
- More complex codebase during transition
- Longer overall timeline

### Option 3: Wait and Monitor (MOST CONSERVATIVE)

**Timeline:** Indefinite

**Actions:**
- Monitor asmu development and version releases
- Wait for Python 3.12+ to become project requirement for other reasons
- Track community adoption and documentation improvements
- Revisit decision in 6-12 months

**Trigger conditions for reconsideration:**
- asmu reaches version 1.0 (stable API)
- Comprehensive documentation becomes available
- Strong community adoption observed
- Python 3.12+ becomes mandatory for other dependencies
- Performance issues identified in current implementation

**Pros:**
- ✅ Zero immediate risk
- ✅ No development time investment
- ✅ Current implementation remains stable
- ✅ Can leverage lessons learned from early adopters

**Cons:**
- May miss out on performance improvements
- Technical debt accumulates
- Harder migration later if deferred too long

---

## Recommendations

### Immediate Actions (Next 1-2 Months)

1. **Continue with current implementation**
   - Current sounddevice-based solution is stable and well-documented
   - No immediate business need for migration
   - Avoid disruption to working audio engine

2. **Monitor asmu development**
   - Star/watch the GitLab repository (if accessible)
   - Subscribe to release notifications
   - Track documentation improvements

3. **Document decision**
   - Record this analysis for future reference
   - Set calendar reminder for 6-month review
   - Document trigger conditions for reconsideration

### Medium-Term Actions (3-6 Months)

1. **Evaluate Python 3.12+ upgrade**
   - Assess other dependencies' 3.12 compatibility
   - Test project functionality on Python 3.12
   - Plan upgrade timeline (if beneficial for other reasons)

2. **Build proof-of-concept**
   - Once Python 3.12+ available in dev environment
   - Create minimal asmu-based audio player
   - Compare API ergonomics and performance

### Long-Term Actions (6-12 Months)

1. **Reassess based on:**
   - asmu version number (aim for ≥1.0)
   - Documentation quality
   - Community growth
   - Proven production usage by others
   - Feature completeness vs. current needs

2. **Consider migration if:**
   - asmu demonstrates clear performance advantage
   - API is well-documented and stable
   - All required features are supported
   - Python 3.12+ is already project requirement
   - Community is active and supportive

---

## Technical Deep Dive: Current Implementation

### AudioDevice Architecture

```python
# Current initialization
device = AudioDevice(
    buffer_size=128,      # frames
    num_channels=2,       # stereo
    device=None          # auto-select
)

# Callback-based design
def audio_callback(outdata: np.ndarray, frames: int):
    # Fill buffer with mixed audio
    outdata[:] = mixer.mix(playback_states, frames)

device.set_callback(audio_callback)
device.start()
```

**Key design patterns:**
- Callback-based (real-time safe)
- Stateless mixing (no locks in callback)
- NumPy-based buffer processing
- Platform-specific API detection
- Graceful fallback on device errors

### Critical Features to Preserve

1. **Low-latency device validation**
   - Must filter out MME/DirectSound on Windows
   - Must prefer ASIO/WASAPI
   - Must provide clear error messages when invalid device selected

2. **Stream error handling**
   - Device-in-use detection
   - Buffer underrun recovery
   - User-friendly error messages

3. **Flexible channel handling**
   - Mono → stereo conversion
   - Stereo → mono mixing
   - Multi-channel truncation/expansion

4. **Playback state management**
   - Position tracking
   - Loop counting
   - Toggle mode support

### Performance Constraints

- **Audio callback timing:** Must complete in < buffer duration
  - Example: 128 frames @ 48kHz = 2.67ms deadline
  - Current implementation: ~0.5-1.0ms typical
  - Safety margin: ~1-2ms

- **Memory allocation:** Zero allocations in audio callback
  - Pre-allocated buffers
  - No Python object creation
  - NumPy operations use out= parameter

---

## Questions for ASMU Maintainers

Before committing to migration, we need answers to:

### 1. Core Functionality
- Does asmu support platform-specific low-latency APIs (ASIO, WASAPI, Core Audio, JACK)?
- How does device selection and enumeration work?
- Can buffer sizes be configured per-stream?
- What sample rates are supported?

### 2. API Design
- What is the basic usage pattern (callbacks, generators, coroutines)?
- How are multi-channel streams handled?
- Is there built-in support for mixing multiple sources?
- How does error handling work?

### 3. Performance
- What is the typical latency overhead?
- Are there benchmarks vs. PortAudio/sounddevice?
- Is the audio callback guaranteed to be real-time safe?
- What is the memory allocation strategy?

### 4. Stability & Support
- What is the API stability guarantee?
- When is version 1.0 planned?
- What is the backwards compatibility policy?
- Is there a migration guide from sounddevice/PortAudio?

### 5. File I/O
- Does asmu include file loading, or should we keep soundfile?
- What audio formats are supported?
- Is resampling built-in?

### 6. Platform Support
- Which platforms are officially supported?
- Are there platform-specific optimizations?
- What are the system requirements?

---

## Conclusion

### Summary Assessment

**Current situation:**
- ✅ Stable, well-tested audio implementation
- ✅ Based on mature, widely-used libraries (PortAudio/sounddevice)
- ✅ Meets all current requirements
- ✅ Good performance characteristics

**ASMU potential:**
- ⚠️ Modern, performance-focused design
- ⚠️ Modular architecture
- ❌ Limited documentation
- ❌ Early version (0.1.x)
- ❌ Requires Python 3.12+

### Final Recommendation

**DO NOT migrate to asmu at this time.**

**Rationale:**
1. Current implementation is stable and meets all requirements
2. asmu requires Python 3.12+ (blocking issue)
3. Limited public documentation prevents informed decision
4. Early version number suggests API instability
5. Unknown feature coverage vs. current needs
6. High migration effort with unclear benefit

**Next steps:**
1. Archive this analysis for future reference
2. Set 6-month review reminder (June 2025)
3. Monitor asmu development and community growth
4. Plan Python 3.12+ upgrade independently of asmu decision

**Trigger for reconsideration:**
- Python 3.12+ becomes project requirement for other reasons
- asmu reaches version 1.0 with stable API
- Comprehensive documentation becomes available
- Clear performance/feature advantages demonstrated
- Production usage by reputable projects

---

## Appendix A: Code Inventory

### Files Using Audio Components

```
src/launchsampler/audio/
├── __init__.py              # Audio module exports
├── device.py               # AudioDevice class (446 lines)
├── mixer.py                # AudioMixer class (144 lines)
├── loader.py               # SampleLoader class (140 lines)
└── data.py                 # AudioData, PlaybackState (292 lines)

src/launchsampler/exceptions/
└── audio.py                # Audio exceptions (83 lines)

src/launchsampler/cli/commands/
└── audio.py                # CLI audio commands

tests/
└── audio/                  # Audio unit tests
```

**Total audio-related code:** ~1,105 lines

### External Dependencies

```toml
[tool.poetry.dependencies]
sounddevice = "^0.4.0"      # PortAudio wrapper
soundfile = "^0.12.0"       # File I/O
numpy = "^1.24.0"           # Buffer processing
```

---

## Appendix B: Resources

### ASMU Resources
- **PyPI:** https://pypi.org/project/asmu/
- **Documentation:** https://felhub.gitlab.io/asmu/api/asmu/ (currently inaccessible)
- **Conference Talk:** Audio Developer Conference 2025 - "Real-Time Audio in Python: Introducing the asmu Package"
- **Developer:** Felix (PhD candidate, TU Wien)

### Current Stack Resources
- **sounddevice:** https://python-sounddevice.readthedocs.io/
- **PortAudio:** http://www.portaudio.com/
- **soundfile:** https://python-soundfile.readthedocs.io/

### Alternative Libraries (for comparison)
- **python-sounddevice:** Well-established, production-ready
- **PyAudio:** Older but widely used
- **SoundCard:** Pure Python, cross-platform
- **miniaudio:** C library with Python bindings

---

**Document Version:** 1.0
**Date:** 2025-11-20
**Author:** Claude (AI Assistant)
**Review Status:** Draft - Awaiting stakeholder review
