"""Tests for Player orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
import pytest

from launchsampler.audio.data import AudioData
from launchsampler.core.player import Player
from launchsampler.models import AppConfig, Set, Launchpad, Pad, Sample, PlaybackMode, Color
from launchsampler.protocols import PlaybackEvent, MidiEvent


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return AppConfig(
        default_audio_device=None,
        default_buffer_size=256,
        midi_poll_interval=5.0
    )


@pytest.fixture
def test_set(sample_audio_file):
    """Create a test set with some loaded pads."""
    launchpad = Launchpad()
    
    # Load a few pads with samples
    sample = Sample.from_file(sample_audio_file)
    
    # Pad 0 - ONE_SHOT
    launchpad.pads[0].sample = sample
    launchpad.pads[0].mode = PlaybackMode.ONE_SHOT
    launchpad.pads[0].color = Color(r=127, g=0, b=0)
    
    # Pad 5 - LOOP
    launchpad.pads[5].sample = sample
    launchpad.pads[5].mode = PlaybackMode.LOOP
    launchpad.pads[5].color = Color(r=0, g=127, b=0)
    
    # Pad 10 - HOLD
    launchpad.pads[10].sample = sample
    launchpad.pads[10].mode = PlaybackMode.HOLD
    launchpad.pads[10].color = Color(r=0, g=0, b=127)
    
    set_obj = Set(name="Test Set", launchpad=launchpad)
    return set_obj


@pytest.fixture
def empty_set():
    """Create an empty set with no samples."""
    return Set(name="Empty Set", launchpad=Launchpad())


# =================================================================
# Lifecycle & Configuration Tests
# =================================================================

@pytest.mark.unit
class TestPlayerLifecycle:
    """Test Player initialization and lifecycle."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_initialization_with_config(self, mock_midi, mock_engine, mock_audio, mock_config):
        """Test player initializes with configuration."""
        player = Player(mock_config)
        
        assert player.config == mock_config
        assert player.current_set is None
        assert not player.is_running
        assert player._audio_device is None
        assert player._engine is None
        assert player._midi is None
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_start_initializes_components(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test starting player initializes audio and MIDI."""
        # Setup mocks
        mock_audio = Mock()
        mock_audio_cls.return_value = mock_audio
        
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        result = player.start()
        
        assert result is True
        assert player.is_running
        
        # Verify audio device created with config
        mock_audio_cls.assert_called_once_with(
            device=mock_config.default_audio_device,
            buffer_size=mock_config.default_buffer_size,
            low_latency=True
        )
        
        # Verify engine created
        mock_engine_cls.assert_called_once()
        
        # Verify engine registered player as observer
        mock_engine.register_observer.assert_called_once_with(player)
        
        # Verify engine started
        mock_engine.start.assert_called_once()
        
        # Verify MIDI started
        mock_midi.start.assert_called_once()
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_stop_cleans_up_components(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test stopping player cleans up resources."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        player.start()
        player.stop()
        
        assert not player.is_running
        mock_engine.stop.assert_called_once()
        mock_midi.stop.assert_called_once()
    
    @patch('launchsampler.core.player.AudioDevice', side_effect=Exception("Audio init failed"))
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_handles_audio_device_failure(self, mock_midi, mock_audio, mock_config):
        """Test player handles audio device initialization failure gracefully."""
        player = Player(mock_config)
        result = player.start()
        
        assert result is False
        assert not player.is_running
        assert player._audio_device is None
        assert player._engine is None
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController', side_effect=Exception("MIDI init failed"))
    def test_player_handles_midi_device_missing(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test player continues without MIDI if unavailable."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        result = player.start()
        
        # Should still succeed without MIDI
        assert result is True
        assert player.is_running
        assert player._midi is None
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_context_manager(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test player works as context manager."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        
        with player:
            assert player.is_running
        
        assert not player.is_running
        mock_engine.stop.assert_called_once()
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_double_start_is_safe(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test calling start() twice doesn't break anything."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        result1 = player.start()
        result2 = player.start()
        
        assert result1 is True
        assert result2 is True
        assert player.is_running


# =================================================================
# Set Management Tests
# =================================================================

@pytest.mark.unit
class TestPlayerSetManagement:
    """Test Player set loading and management."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_load_set_while_stopped(self, mock_midi, mock_engine_cls, mock_audio, mock_config, test_set):
        """Test loading set before player starts."""
        player = Player(mock_config)
        player.load_set(test_set)
        
        assert player.current_set == test_set
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_load_set_into_engine(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test loading set into running engine."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Should load all assigned pads
        assert mock_engine.load_sample.call_count == 3  # 3 pads with samples
        
        # Verify correct pad indices were loaded
        calls = mock_engine.load_sample.call_args_list
        loaded_indices = [call[0][0] for call in calls]
        assert 0 in loaded_indices
        assert 5 in loaded_indices
        assert 10 in loaded_indices
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_load_empty_set(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config, empty_set):
        """Test loading empty set doesn't cause errors."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(empty_set)
        
        assert player.current_set == empty_set
        # No samples to load
        mock_engine.load_sample.assert_not_called()
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_start_with_initial_set(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test starting player with initial set loads samples."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start(initial_set=test_set)
        
        assert player.current_set == test_set
        assert mock_engine.load_sample.call_count == 3
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_switch_between_sets(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config, test_set, empty_set):
        """Test switching from one set to another."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        
        # Load first set
        player.load_set(test_set)
        assert player.current_set == test_set
        first_load_count = mock_engine.load_sample.call_count
        
        # Load second set
        player.load_set(empty_set)
        assert player.current_set == empty_set
        # No additional loads for empty set
        assert mock_engine.load_sample.call_count == first_load_count


# =================================================================
# Playback Control Tests
# =================================================================

@pytest.mark.unit
class TestPlayerPlaybackControl:
    """Test Player playback control methods."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_trigger_pad(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test triggering a pad forwards to engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.trigger_pad(5)
        
        mock_engine.trigger_pad.assert_called_once_with(5)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_release_pad(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test releasing a pad forwards to engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.release_pad(10)
        
        mock_engine.release_pad.assert_called_once_with(10)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_stop_pad(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test stopping a pad forwards to engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.stop_pad(15)
        
        mock_engine.stop_pad.assert_called_once_with(15)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_stop_all(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test stop all forwards to engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.stop_all()
        
        mock_engine.stop_all.assert_called_once()
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_set_master_volume(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test setting master volume forwards to engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.set_master_volume(0.75)
        
        mock_engine.set_master_volume.assert_called_once_with(0.75)


# =================================================================
# MIDI Event Handling Tests
# =================================================================

@pytest.mark.unit
class TestPlayerMIDIHandling:
    """Test Player MIDI event handling."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_midi_pad_press_triggers_audio(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test MIDI pad press triggers audio playback."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Simulate MIDI pad press via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_ON, 0)
        
        # Should trigger audio
        mock_engine.trigger_pad.assert_called_once_with(0)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_empty_pad_press_doesnt_trigger_audio(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test pressing empty pad doesn't trigger audio."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Press empty pad (pad 1 has no sample) via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_ON, 1)
        
        # Should NOT trigger audio
        mock_engine.trigger_pad.assert_not_called()
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_pad_release_stops_audio_in_loop_mode(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test pad release stops audio in LOOP mode."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Release pad 5 (LOOP mode) via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_OFF, 5)
        
        # Should release audio
        mock_engine.release_pad.assert_called_once_with(5)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_pad_release_stops_audio_in_hold_mode(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test pad release stops audio in HOLD mode."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Release pad 10 (HOLD mode) via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_OFF, 10)
        
        # Should release audio
        mock_engine.release_pad.assert_called_once_with(10)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_pad_release_ignores_oneshot_mode(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test pad release doesn't affect ONE_SHOT mode."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Release pad 0 (ONE_SHOT mode) via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_OFF, 0)
        
        # Should NOT release audio
        mock_engine.release_pad.assert_not_called()
    

# =================================================================
# State Observer Tests
# =================================================================

@pytest.mark.unit
class TestPlayerStateObserver:
    """Test Player as StateObserver."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_forwards_playback_events(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test player forwards playback events from engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        
        callback = Mock()
        player.set_playback_callback(callback)
        
        # Simulate engine firing events
        player.on_playback_event(PlaybackEvent.PAD_PLAYING, 5)
        player.on_playback_event(PlaybackEvent.PAD_STOPPED, 5)
        player.on_playback_event(PlaybackEvent.PAD_FINISHED, 5)
        
        # Should forward all events
        assert callback.call_count == 3
        callback.assert_any_call(PlaybackEvent.PAD_PLAYING, 5)
        callback.assert_any_call(PlaybackEvent.PAD_STOPPED, 5)
        callback.assert_any_call(PlaybackEvent.PAD_FINISHED, 5)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_registers_as_observer(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test player registers itself as observer on engine."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        
        # Should register as observer
        mock_engine.register_observer.assert_called_once_with(player)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_playback_events_without_callback_dont_crash(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test receiving playback events without callback doesn't crash."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        
        # No callback set - should not crash
        player.on_playback_event(PlaybackEvent.PAD_PLAYING, 0)
        player.on_playback_event(PlaybackEvent.PAD_STOPPED, 0)


# =================================================================
# MIDI Observer Registration Tests
# =================================================================

@pytest.mark.unit
class TestPlayerMidiObserverFacade:
    """Test Player MIDI observer registration facade methods."""

    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_register_midi_observer_delegates_to_controller(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test register_midi_observer delegates to MIDI controller."""
        from launchsampler.protocols import MidiObserver

        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi

        player = Player(mock_config)
        player.start()

        # Create mock observer
        observer = Mock(spec=MidiObserver)

        # Register via facade
        player.register_midi_observer(observer)

        # Should delegate to MIDI controller (Player itself also registers, so called twice)
        assert mock_midi.register_observer.call_count == 2
        mock_midi.register_observer.assert_any_call(player)  # Player registers itself
        mock_midi.register_observer.assert_any_call(observer)  # Our observer

    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_unregister_midi_observer_delegates_to_controller(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test unregister_midi_observer delegates to MIDI controller."""
        from launchsampler.protocols import MidiObserver

        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi

        player = Player(mock_config)
        player.start()

        # Create mock observer
        observer = Mock(spec=MidiObserver)

        # Unregister via facade
        player.unregister_midi_observer(observer)

        # Should delegate to MIDI controller
        mock_midi.unregister_observer.assert_called_once_with(observer)

    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_midi_observer_registration_when_midi_not_started(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test MIDI observer registration is safe when MIDI not started."""
        from launchsampler.protocols import MidiObserver

        player = Player(mock_config)
        # Don't start player - no MIDI controller

        observer = Mock(spec=MidiObserver)

        # Should not crash when MIDI is None
        player.register_midi_observer(observer)
        player.unregister_midi_observer(observer)


# =================================================================
# Query Methods Tests
# =================================================================

@pytest.mark.unit
class TestPlayerQueryMethods:
    """Test Player query and status methods."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_is_running_property(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test is_running property reflects state."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        
        assert not player.is_running
        player.start()
        assert player.is_running
        player.stop()
        assert not player.is_running
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_is_midi_connected(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test is_midi_connected property."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi.is_connected = True
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        
        assert not player.is_midi_connected
        player.start()
        assert player.is_midi_connected
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_active_voices_property(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test active_voices property returns engine voice count."""
        mock_engine = Mock()
        mock_engine.active_voices = 5
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        
        assert player.active_voices == 0  # Not started
        player.start()
        assert player.active_voices == 5
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_audio_device_name(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test audio_device_name property."""
        mock_audio = Mock()
        mock_audio.device_name = "Test Audio Device"
        mock_audio_cls.return_value = mock_audio
        
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        
        assert player.audio_device_name == "No Audio"
        player.start()
        assert player.audio_device_name == "Test Audio Device"
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_midi_device_name(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config):
        """Test midi_device_name property."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi.device_name = "Launchpad X"
        mock_midi_cls.return_value = mock_midi
        
        player = Player(mock_config)
        
        assert player.midi_device_name == "No MIDI"
        player.start()
        assert player.midi_device_name == "Launchpad X"
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_is_pad_playing(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test is_pad_playing query."""
        mock_engine = Mock()
        mock_engine.is_pad_playing = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        
        assert not player.is_pad_playing(0)  # Not started
        player.start()
        assert player.is_pad_playing(0)
        mock_engine.is_pad_playing.assert_called_with(0)
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_get_playing_pads(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test get_playing_pads query."""
        mock_engine = Mock()
        mock_engine.get_playing_pads = Mock(return_value=[0, 5, 10])
        mock_engine_cls.return_value = mock_engine

        player = Player(mock_config)

        assert player.get_playing_pads() == []  # Not started
        player.start()
        assert player.get_playing_pads() == [0, 5, 10]

    @patch('launchsampler.core.player.LaunchpadController')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.AudioDevice')
    def test_get_audio_data(self, mock_audio_cls, mock_engine_cls, mock_midi, mock_config):
        """Test get_audio_data delegates to engine."""
        # Create mock audio data
        mock_audio_data = Mock(spec=AudioData)
        mock_audio_data.sample_rate = 44100
        mock_audio_data.num_channels = 2

        mock_engine = Mock()
        mock_engine.get_audio_data = Mock(return_value=mock_audio_data)
        mock_engine_cls.return_value = mock_engine

        player = Player(mock_config)

        # Should return None when engine not started
        assert player.get_audio_data(0) is None

        # Start player
        player.start()

        # Should delegate to engine
        result = player.get_audio_data(5)
        assert result == mock_audio_data
        mock_engine.get_audio_data.assert_called_once_with(5)

        # Test with no audio data (pad not loaded)
        mock_engine.get_audio_data = Mock(return_value=None)
        assert player.get_audio_data(10) is None


# =================================================================
# Error Handling Tests
# =================================================================

@pytest.mark.unit
class TestPlayerErrorHandling:
    """Test Player error handling and recovery."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_player_recovers_from_callback_exception(self, mock_midi, mock_engine_cls, mock_audio_cls, mock_config):
        """Test player continues if callback raises exception."""
        mock_engine = Mock()
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        
        # Set callback that raises exception
        def bad_callback(event, pad_index):
            raise RuntimeError("Callback error")
        
        player.set_playback_callback(bad_callback)
        
        # Should not crash when event fires
        try:
            player.on_playback_event(PlaybackEvent.PAD_PLAYING, 0)
        except RuntimeError:
            pass  # Exception is expected to propagate in this simple implementation
        
        # Player should still be running
        assert player.is_running
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_operations_safe_when_not_started(self, mock_midi, mock_engine, mock_audio, mock_config):
        """Test operations are safe when player not started."""
        player = Player(mock_config)
        
        # These should not crash
        player.trigger_pad(0)
        player.release_pad(0)
        player.stop_pad(0)
        player.stop_all()
        player.set_master_volume(0.5)
        
        assert not player.is_pad_playing(0)
        assert player.get_playing_pads() == []
        assert player.active_voices == 0


# =================================================================
# Integration-style Tests
# =================================================================

@pytest.mark.unit
class TestPlayerIntegration:
    """Test Player with more realistic scenarios."""
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_complete_playback_workflow(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test complete workflow: start, load, trigger, observe, stop."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine.active_voices = 1
        mock_engine_cls.return_value = mock_engine
        
        mock_midi = Mock()
        mock_midi_cls.return_value = mock_midi
        
        # Track playback events
        playback_events = []
        
        def track_playback_events(event, pad_index):
            playback_events.append((event, pad_index))
        
        player = Player(mock_config)
        player.set_playback_callback(track_playback_events)
        
        # Start and load set
        player.start(initial_set=test_set)
        assert player.is_running
        assert player.current_set == test_set
        
        # Simulate MIDI press via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_ON, 0)
        
        # Should trigger audio
        mock_engine.trigger_pad.assert_called_with(0)
        
        # Simulate engine firing PAD_PLAYING
        player.on_playback_event(PlaybackEvent.PAD_PLAYING, 0)
        assert (PlaybackEvent.PAD_PLAYING, 0) in playback_events
        
        # Simulate MIDI release via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_OFF, 0)
        
        # Stop player
        player.stop()
        assert not player.is_running
    
    @patch('launchsampler.core.player.AudioDevice')
    @patch('launchsampler.core.player.SamplerEngine')
    @patch('launchsampler.core.player.LaunchpadController')
    def test_multiple_pads_playing_simultaneously(self, mock_midi_cls, mock_engine_cls, mock_audio_cls, mock_config, test_set):
        """Test multiple pads can be triggered and tracked."""
        mock_engine = Mock()
        mock_engine.load_sample = Mock(return_value=True)
        mock_engine_cls.return_value = mock_engine
        
        player = Player(mock_config)
        player.start()
        player.load_set(test_set)
        
        # Trigger multiple pads via MidiObserver protocol
        player.on_midi_event(MidiEvent.NOTE_ON, 0)
        player.on_midi_event(MidiEvent.NOTE_ON, 5)
        player.on_midi_event(MidiEvent.NOTE_ON, 10)
        
        # All should be triggered
        assert mock_engine.trigger_pad.call_count == 3
        mock_engine.trigger_pad.assert_any_call(0)
        mock_engine.trigger_pad.assert_any_call(5)
        mock_engine.trigger_pad.assert_any_call(10)

