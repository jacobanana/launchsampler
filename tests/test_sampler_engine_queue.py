"""Tests for SamplerEngine queue system and voice management."""

from unittest.mock import Mock

import numpy as np
import pytest

from launchsampler.audio import AudioDevice
from launchsampler.audio.data import AudioData
from launchsampler.core.sampler_engine import SamplerEngine
from launchsampler.models import AudioSample, Pad, PlaybackMode
from launchsampler.protocols import PlaybackEvent


@pytest.fixture
def mock_audio_device():
    """Create a mock audio device."""
    device = Mock(spec=AudioDevice)
    device.sample_rate = 44100
    device.num_channels = 2
    device.is_running = False
    return device


@pytest.fixture
def engine(mock_audio_device):
    """Create a SamplerEngine with mock audio device."""
    return SamplerEngine(mock_audio_device, num_pads=64)


@pytest.fixture
def loaded_engine(engine, sample_audio_file):
    """Create an engine with a few samples loaded."""
    sample = AudioSample.from_file(sample_audio_file)

    # Load pad 0 - ONE_SHOT
    pad0 = Pad(x=0, y=0)
    pad0.sample = sample
    pad0.mode = PlaybackMode.ONE_SHOT
    pad0.volume = 1.0
    engine.load_sample(0, pad0)

    # Load pad 5 - LOOP
    pad5 = Pad(x=5, y=0)
    pad5.sample = sample
    pad5.mode = PlaybackMode.LOOP
    pad5.volume = 0.8
    engine.load_sample(5, pad5)

    # Load pad 10 - HOLD
    pad10 = Pad(x=2, y=1)
    pad10.sample = sample
    pad10.mode = PlaybackMode.HOLD
    pad10.volume = 0.6
    engine.load_sample(10, pad10)

    # Load pad 15 - LOOP_TOGGLE
    pad15 = Pad(x=7, y=1)
    pad15.sample = sample
    pad15.mode = PlaybackMode.LOOP_TOGGLE
    pad15.volume = 1.0
    engine.load_sample(15, pad15)

    # Load pad 20 - TOGGLE
    pad20 = Pad(x=4, y=2)
    pad20.sample = sample
    pad20.mode = PlaybackMode.TOGGLE
    pad20.volume = 1.0
    engine.load_sample(20, pad20)

    return engine


# =================================================================
# Queue System Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineQueue:
    """Test audio callback queue processing."""

    def test_trigger_action_queued(self, loaded_engine):
        """Test trigger action is queued."""
        loaded_engine.trigger_pad(0)

        # Action should be in queue
        assert not loaded_engine._trigger_queue.empty()
        action, pad_index = loaded_engine._trigger_queue.get()
        assert action == "trigger"
        assert pad_index == 0

    def test_release_action_queued(self, loaded_engine):
        """Test release action is queued."""
        loaded_engine.release_pad(5)

        # Action should be in queue
        assert not loaded_engine._trigger_queue.empty()
        action, pad_index = loaded_engine._trigger_queue.get()
        assert action == "release"
        assert pad_index == 5

    def test_stop_action_queued(self, loaded_engine):
        """Test stop action is queued."""
        loaded_engine.stop_pad(10)

        # Action should be in queue
        assert not loaded_engine._trigger_queue.empty()
        action, pad_index = loaded_engine._trigger_queue.get()
        assert action == "stop"
        assert pad_index == 10

    def test_multiple_actions_queued(self, loaded_engine):
        """Test multiple actions are queued in order."""
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        loaded_engine.release_pad(10)
        loaded_engine.stop_pad(15)

        # Check queue has all actions in order
        action1, pad1 = loaded_engine._trigger_queue.get()
        assert (action1, pad1) == ("trigger", 0)

        action2, pad2 = loaded_engine._trigger_queue.get()
        assert (action2, pad2) == ("trigger", 5)

        action3, pad3 = loaded_engine._trigger_queue.get()
        assert (action3, pad3) == ("release", 10)

        action4, pad4 = loaded_engine._trigger_queue.get()
        assert (action4, pad4) == ("stop", 15)

    def test_queue_processes_trigger_in_callback(self, loaded_engine):
        """Test queue trigger action is processed in audio callback."""
        # Queue a trigger
        loaded_engine.trigger_pad(0)

        # Simulate audio callback
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Queue should be empty (processed)
        assert loaded_engine._trigger_queue.empty()

        # Pad should be playing
        assert loaded_engine.is_pad_playing(0)

    def test_queue_processes_release_in_callback(self, loaded_engine):
        """Test queue release action is processed in audio callback."""
        # Start HOLD mode pad playing (pad 10)
        loaded_engine.trigger_pad(10)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(10)

        # Queue release
        loaded_engine.release_pad(10)

        # Process release in callback
        loaded_engine._audio_callback(outdata, 512)

        # Queue should be empty
        assert loaded_engine._trigger_queue.empty()

        # Pad should be stopped (HOLD mode responds to release)
        assert not loaded_engine.is_pad_playing(10)

    def test_queue_processes_stop_in_callback(self, loaded_engine):
        """Test queue stop action is processed in audio callback."""
        # Start pad playing
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(0)

        # Queue stop
        loaded_engine.stop_pad(0)

        # Process stop in callback
        loaded_engine._audio_callback(outdata, 512)

        # Pad should be stopped
        assert not loaded_engine.is_pad_playing(0)

    def test_queue_handles_concurrent_triggers(self, loaded_engine):
        """Test queue can handle multiple simultaneous triggers."""
        # Trigger multiple pads
        for pad_index in [0, 5, 10, 15]:
            loaded_engine.trigger_pad(pad_index)

        # Process all in one callback
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # All pads should be playing
        assert loaded_engine.is_pad_playing(0)
        assert loaded_engine.is_pad_playing(5)
        assert loaded_engine.is_pad_playing(10)
        assert loaded_engine.is_pad_playing(15)

    def test_queue_ignores_unloaded_pads(self, loaded_engine):
        """Test queue processing ignores triggers for unloaded pads."""
        # Trigger unloaded pad (pad 25 is not loaded)
        loaded_engine.trigger_pad(25)

        # Process in callback
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should not crash, pad should not be playing
        assert not loaded_engine.is_pad_playing(25)

    def test_queue_full_drops_trigger(self, loaded_engine):
        """Test queue drops triggers when full rather than blocking."""
        # Fill the queue (256 entries)
        for _i in range(256):
            loaded_engine.trigger_pad(0)

        # Queue should be full
        assert loaded_engine._trigger_queue.full()

        # Additional trigger should be dropped (logged but not raise)
        loaded_engine.trigger_pad(0)  # Should not block


# =================================================================
# Voice Management Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineVoiceManagement:
    """Test voice counting and management."""

    def test_active_voices_count_starts_zero(self, loaded_engine):
        """Test active voices count starts at zero."""
        assert loaded_engine.active_voices == 0

    def test_active_voices_increments_on_trigger(self, loaded_engine):
        """Test active voices increments when pad triggered."""
        loaded_engine.trigger_pad(0)

        # Process trigger
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        assert loaded_engine.active_voices == 1

    def test_active_voices_counts_multiple_pads(self, loaded_engine):
        """Test active voices counts multiple playing pads."""
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        loaded_engine.trigger_pad(10)

        # Process all triggers
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        assert loaded_engine.active_voices == 3

    def test_active_voices_decrements_on_stop(self, loaded_engine):
        """Test active voices decrements when pad stopped."""
        # Start playing
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.active_voices == 2

        # Stop one pad
        loaded_engine.stop_pad(0)
        loaded_engine._audio_callback(outdata, 512)

        assert loaded_engine.active_voices == 1

    def test_active_voices_accurate_after_finish(self, loaded_engine):
        """Test active voices is accurate when pads finish naturally."""
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Force the pad to finish by setting position past end and making it detect the finish
        state = loaded_engine._playback_states[0]
        if state.audio_data:
            # Set position near end
            state.position = state.audio_data.num_frames - 100

        # Next callback should play remaining frames and detect finish
        loaded_engine._audio_callback(outdata, 512)

        # Voice count should be 0 (pad finished)
        assert loaded_engine.active_voices == 0

    def test_get_playing_pads_empty_initially(self, loaded_engine):
        """Test get_playing_pads returns empty list initially."""
        assert loaded_engine.get_playing_pads() == []

    def test_get_playing_pads_returns_active_indices(self, loaded_engine):
        """Test get_playing_pads returns correct pad indices."""
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        loaded_engine.trigger_pad(10)

        # Process triggers
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        playing = loaded_engine.get_playing_pads()
        assert set(playing) == {0, 5, 10}

    def test_stop_all_clears_all_voices(self, loaded_engine):
        """Test stop_all stops all playing pads."""
        # Start multiple pads
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        loaded_engine.trigger_pad(10)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.active_voices == 3

        # Stop all - queues stop actions for all pads
        loaded_engine.stop_all()

        # Process the queue to actually stop the pads
        loaded_engine._audio_callback(outdata, 512)

        # Voices should be stopped after processing
        assert loaded_engine.active_voices == 0


# =================================================================
# Playback Mode Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEnginePlaybackModes:
    """Test different playback modes."""

    def test_oneshot_mode_plays_to_end(self, loaded_engine):
        """Test ONE_SHOT mode plays sample fully."""
        # Trigger ONE_SHOT pad
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(0)

        # Release should not stop ONE_SHOT
        loaded_engine.release_pad(0)
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing
        assert loaded_engine.is_pad_playing(0)

    def test_loop_mode_repeats(self, loaded_engine):
        """Test LOOP mode continues looping."""
        # Trigger LOOP pad
        loaded_engine.trigger_pad(5)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        state = loaded_engine._playback_states[5]
        assert state.mode == PlaybackMode.LOOP
        assert state.is_playing

    def test_loop_mode_ignores_release(self, loaded_engine):
        """Test LOOP mode continues playing after release (unlike HOLD)."""
        # Start LOOP
        loaded_engine.trigger_pad(5)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(5)

        # Release - should keep playing
        loaded_engine.release_pad(5)
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing (LOOP ignores release)
        assert loaded_engine.is_pad_playing(5)

    def test_hold_mode_stops_on_release(self, loaded_engine):
        """Test HOLD mode stops when released."""
        # Start HOLD
        loaded_engine.trigger_pad(10)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(10)

        # Release
        loaded_engine.release_pad(10)
        loaded_engine._audio_callback(outdata, 512)

        # Should be stopped
        assert not loaded_engine.is_pad_playing(10)

    def test_loop_toggle_mode_toggles_on_trigger(self, loaded_engine):
        """Test LOOP_TOGGLE mode toggles playback."""
        # First trigger - should start playing
        loaded_engine.trigger_pad(15)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(15)

        # Second trigger - should stop
        loaded_engine.trigger_pad(15)
        loaded_engine._audio_callback(outdata, 512)
        assert not loaded_engine.is_pad_playing(15)

        # Third trigger - should start again
        loaded_engine.trigger_pad(15)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(15)

    def test_loop_toggle_ignores_release(self, loaded_engine):
        """Test LOOP_TOGGLE mode ignores release messages."""
        # Start playing
        loaded_engine.trigger_pad(15)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(15)

        # Release should be ignored
        loaded_engine.release_pad(15)
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing
        assert loaded_engine.is_pad_playing(15)

    def test_oneshot_mode_restarts_on_trigger(self, loaded_engine):
        """Test ONE_SHOT mode restarts playback on each trigger."""
        # First trigger - should start playing
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(0)

        # Get initial position
        state = loaded_engine._playback_states[0]
        initial_position = state.position

        # Let it play a bit
        loaded_engine._audio_callback(outdata, 512)
        assert state.position > initial_position

        # Second trigger - should restart from beginning
        loaded_engine.trigger_pad(0)
        loaded_engine._audio_callback(outdata, 512)
        # Position should be reset (close to 0, accounting for the frames just processed)
        assert state.position < initial_position + 1024  # Within 2 callback frames
        assert loaded_engine.is_pad_playing(0)

    def test_toggle_mode_toggles_on_trigger(self, loaded_engine):
        """Test TOGGLE mode toggles playback on/off."""
        # First trigger - should start playing
        loaded_engine.trigger_pad(20)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(20)

        # Second trigger - should stop
        loaded_engine.trigger_pad(20)
        loaded_engine._audio_callback(outdata, 512)
        assert not loaded_engine.is_pad_playing(20)

        # Third trigger - should start again
        loaded_engine.trigger_pad(20)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(20)

    def test_toggle_ignores_release(self, loaded_engine):
        """Test TOGGLE mode ignores release messages."""
        # Start playing
        loaded_engine.trigger_pad(20)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(20)

        # Release - should keep playing
        loaded_engine.release_pad(20)
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing
        assert loaded_engine.is_pad_playing(20)

    def test_oneshot_ignores_release(self, loaded_engine):
        """Test ONE_SHOT mode ignores release messages."""
        # Start playing
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(0)

        # Release should be ignored
        loaded_engine.release_pad(0)
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing
        assert loaded_engine.is_pad_playing(0)

    def test_trigger_mode_restarts_sample(self, loaded_engine):
        """Test triggering a playing pad restarts it (LOOP/HOLD modes)."""
        # Trigger pad 5 (LOOP mode)
        loaded_engine.trigger_pad(5)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Advance position
        state = loaded_engine._playback_states[5]
        initial_position = state.position
        for _ in range(5):
            loaded_engine._audio_callback(outdata, 512)

        # Position should have advanced
        assert state.position > initial_position

        # Trigger again - should restart
        loaded_engine.trigger_pad(5)
        loaded_engine._audio_callback(outdata, 512)

        # Position should be back near start (starts at 0 + one callback worth of frames)
        assert state.position < 1000  # Should be near beginning


# =================================================================
# State Machine Event Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineEvents:
    """Test state machine event firing."""

    def test_pad_triggered_event_fired(self, loaded_engine):
        """Test PAD_TRIGGERED event is fired on trigger."""
        observer = Mock()
        loaded_engine.register_observer(observer)

        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should have fired PAD_TRIGGERED
        observer.on_playback_event.assert_any_call(PlaybackEvent.PAD_TRIGGERED, 0)

    def test_pad_playing_event_fired(self, loaded_engine):
        """Test PAD_PLAYING event is fired when playback starts."""
        observer = Mock()
        loaded_engine.register_observer(observer)

        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should have fired PAD_PLAYING
        observer.on_playback_event.assert_any_call(PlaybackEvent.PAD_PLAYING, 0)

    def test_pad_stopped_event_fired(self, loaded_engine):
        """Test PAD_STOPPED event is fired when pad stopped."""
        observer = Mock()
        loaded_engine.register_observer(observer)

        # Start playing
        loaded_engine.trigger_pad(5)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        observer.reset_mock()

        # Stop
        loaded_engine.stop_pad(5)
        loaded_engine._audio_callback(outdata, 512)

        # Should have fired PAD_STOPPED
        observer.on_playback_event.assert_called_with(PlaybackEvent.PAD_STOPPED, 5)

    def test_pad_finished_event_fired(self, loaded_engine):
        """Test PAD_FINISHED event is fired when pad finishes naturally."""
        observer = Mock()
        loaded_engine.register_observer(observer)

        # Start playing
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Force finish by setting position near end
        state = loaded_engine._playback_states[0]
        if state.audio_data:
            state.position = state.audio_data.num_frames - 100

        observer.reset_mock()
        loaded_engine._audio_callback(outdata, 512)

        # Should have fired PAD_FINISHED
        observer.on_playback_event.assert_called_with(PlaybackEvent.PAD_FINISHED, 0)

    def test_multiple_observers_receive_events(self, loaded_engine):
        """Test multiple observers all receive events."""
        observer1 = Mock()
        observer2 = Mock()
        loaded_engine.register_observer(observer1)
        loaded_engine.register_observer(observer2)

        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Both should receive events
        assert observer1.on_playback_event.called
        assert observer2.on_playback_event.called

    def test_observer_exception_doesnt_crash_callback(self, loaded_engine):
        """Test observer exception doesn't crash audio callback."""
        # Observer that raises exception
        bad_observer = Mock()
        bad_observer.on_playback_event.side_effect = RuntimeError("Observer error")

        good_observer = Mock()

        loaded_engine.register_observer(bad_observer)
        loaded_engine.register_observer(good_observer)

        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)

        # Should not crash
        loaded_engine._audio_callback(outdata, 512)

        # Good observer should still receive events
        assert good_observer.on_playback_event.called


# =================================================================
# Thread Safety Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineThreadSafety:
    """Test thread safety of operations."""

    def test_concurrent_trigger_and_stop(self, loaded_engine):
        """Test triggering and stopping concurrently doesn't cause issues."""
        loaded_engine.trigger_pad(0)
        loaded_engine.stop_pad(0)

        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should process both without crashing
        # Final state depends on order, but should be valid

    def test_trigger_during_callback_simulation(self, loaded_engine):
        """Test triggering while callback is processing is safe."""
        # Start one pad
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Queue another trigger (simulating concurrent input)
        loaded_engine.trigger_pad(5)

        # Next callback should process it
        loaded_engine._audio_callback(outdata, 512)

        assert loaded_engine.is_pad_playing(5)

    def test_volume_change_during_playback(self, loaded_engine):
        """Test changing volume during playback is safe."""
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Change volume
        loaded_engine.update_pad_volume(0, 0.5)

        # Continue playback
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing with new volume
        assert loaded_engine.is_pad_playing(0)
        state = loaded_engine._playback_states[0]
        assert state.volume == 0.5

    def test_mode_change_during_playback(self, loaded_engine):
        """Test changing mode during playback is safe."""
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Change mode
        loaded_engine.update_pad_mode(0, PlaybackMode.LOOP)

        # Continue playback
        loaded_engine._audio_callback(outdata, 512)

        # Should still be playing with new mode
        assert loaded_engine.is_pad_playing(0)
        state = loaded_engine._playback_states[0]
        assert state.mode == PlaybackMode.LOOP

    def test_unload_sample_stops_playback(self, loaded_engine):
        """Test unloading sample during playback stops it safely."""
        loaded_engine.trigger_pad(0)
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)
        assert loaded_engine.is_pad_playing(0)

        # Unload removes the playback state entirely for clean reload
        loaded_engine.unload_sample(0)

        # Playback state should be removed
        assert 0 not in loaded_engine._playback_states
        # Pad should no longer be playing
        assert not loaded_engine.is_pad_playing(0)


# =================================================================
# Audio Mixing Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineAudioMixing:
    """Test audio mixing behavior."""

    def test_callback_generates_audio(self, loaded_engine):
        """Test audio callback generates non-zero audio."""
        loaded_engine.trigger_pad(0)

        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should have generated some audio
        assert np.any(outdata != 0.0)

    def test_callback_without_playing_pads_is_silent(self, loaded_engine):
        """Test callback with no playing pads outputs silence."""
        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should be silent
        assert np.all(outdata == 0.0)

    def test_multiple_pads_mixed(self, loaded_engine):
        """Test multiple pads are mixed together."""
        # Trigger multiple pads
        loaded_engine.trigger_pad(0)
        loaded_engine.trigger_pad(5)
        loaded_engine.trigger_pad(10)

        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Should have audio
        assert np.any(outdata != 0.0)
        assert loaded_engine.active_voices == 3

    def test_master_volume_applied(self, loaded_engine):
        """Test master volume affects output."""
        loaded_engine.trigger_pad(0)

        # Get audio at full volume
        outdata_full = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata_full, 512)
        max_full = np.max(np.abs(outdata_full))

        # Reset and try with lower volume
        loaded_engine.stop_all()
        loaded_engine.set_master_volume(0.5)
        loaded_engine.trigger_pad(0)

        outdata_half = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata_half, 512)
        max_half = np.max(np.abs(outdata_half))

        # Half volume should be quieter
        assert max_half < max_full

    def test_soft_clipping_applied(self, loaded_engine):
        """Test soft clipping prevents values exceeding [-1, 1]."""
        # Trigger many pads to potentially cause clipping
        for i in [0, 5, 10]:
            loaded_engine.trigger_pad(i)

        outdata = np.zeros((512, 2), dtype=np.float32)
        loaded_engine._audio_callback(outdata, 512)

        # Values should be within valid range (after soft clipping)
        assert np.all(outdata >= -1.0)
        assert np.all(outdata <= 1.0)

    def test_callback_exception_outputs_silence(self, loaded_engine):
        """Test callback exception results in silent output."""
        # Force an exception by corrupting state
        loaded_engine._playback_states[0] = None  # This will cause an error
        loaded_engine.trigger_pad(0)

        outdata = np.zeros((512, 2), dtype=np.float32)
        # Should not crash
        loaded_engine._audio_callback(outdata, 512)

        # Should output silence on error
        assert np.all(outdata == 0.0)


# =================================================================
# Sample Loading and Caching Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEngineSampleManagement:
    """Test sample loading and caching."""

    def test_load_sample_caches_audio_data(self, engine, sample_audio_file):
        """Test loading sample caches audio data."""
        sample = AudioSample.from_file(sample_audio_file)
        pad = Pad(x=0, y=0)
        pad.sample = sample
        pad.mode = PlaybackMode.ONE_SHOT

        assert len(engine._audio_cache) == 0
        engine.load_sample(0, pad)

        # Should be cached
        assert len(engine._audio_cache) == 1
        assert str(sample_audio_file) in engine._audio_cache

    def test_load_same_sample_multiple_pads_uses_cache(self, engine, sample_audio_file):
        """Test loading same sample on multiple pads uses cache."""
        sample = AudioSample.from_file(sample_audio_file)

        pad0 = Pad(x=0, y=0)
        pad0.sample = sample
        pad0.mode = PlaybackMode.ONE_SHOT

        pad1 = Pad(x=1, y=0)
        pad1.sample = sample
        pad1.mode = PlaybackMode.LOOP

        engine.load_sample(0, pad0)
        engine.load_sample(1, pad1)

        # Should only have one cached entry
        assert len(engine._audio_cache) == 1

        # Both pads should reference same audio data
        assert engine._playback_states[0].audio_data is engine._playback_states[1].audio_data

    def test_clear_cache_removes_all_entries(self, loaded_engine):
        """Test clear_cache removes all cached audio."""
        assert len(loaded_engine._audio_cache) > 0

        loaded_engine.clear_cache()

        assert len(loaded_engine._audio_cache) == 0

    def test_load_invalid_pad_index_fails(self, engine, sample_audio_file):
        """Test loading with invalid pad index fails gracefully."""
        sample = AudioSample.from_file(sample_audio_file)
        pad = Pad(x=0, y=0)
        pad.sample = sample

        result = engine.load_sample(100, pad)  # Invalid index
        assert result is False

    def test_load_empty_pad_fails(self, engine):
        """Test loading empty pad (no sample) fails gracefully."""
        pad = Pad(x=0, y=0)  # No sample assigned

        result = engine.load_sample(0, pad)
        assert result is False


# =================================================================
# Playback Info Tests
# =================================================================


@pytest.mark.unit
class TestSamplerEnginePlaybackInfo:
    """Test playback information queries."""

    def test_get_playback_info_unloaded_pad_returns_none(self, engine):
        """Test getting info for unloaded pad returns None."""
        info = engine.get_playback_info(0)
        assert info is None

    def test_get_playback_info_loaded_pad(self, loaded_engine):
        """Test getting info for loaded pad."""
        info = loaded_engine.get_playback_info(0)

        assert info is not None
        assert "is_playing" in info
        assert "progress" in info
        assert "mode" in info
        assert "volume" in info

    def test_get_audio_data_returns_loaded_audio(self, loaded_engine):
        """Test get_audio_data returns AudioData."""
        audio_data = loaded_engine.get_audio_data(0)

        assert audio_data is not None
        assert isinstance(audio_data, AudioData)

    def test_get_audio_info_returns_metadata(self, loaded_engine):
        """Test get_audio_info returns file metadata."""
        info = loaded_engine.get_audio_info(0)

        assert info is not None
        assert "duration" in info
        assert "sample_rate" in info
        assert "num_channels" in info
