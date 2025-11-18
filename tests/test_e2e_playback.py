"""End-to-end playback integration tests.

Tests the complete playback pipeline from sample loading through audio output.
These tests verify that all components work together correctly.
"""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import numpy as np

from launchsampler.app import LaunchpadSamplerApp
from launchsampler.models import AppConfig, Set, Sample, PlaybackMode, Color
from launchsampler.protocols import MidiEvent


@pytest.fixture
def config():
    """Create test configuration."""
    return AppConfig(
        default_audio_device=None,
        default_buffer_size=256,
        midi_poll_interval=5.0
    )


@pytest.mark.integration
class TestCompletePlaybackFlow:
    """Test complete playback pipeline from load to audio output."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_load_sample_assign_trigger_plays(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test complete flow: Load sample → Assign to pad → Trigger → Audio plays."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        # Create app and initialize
        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load a sample
        sample = Sample.from_file(sample_audio_file)

        # Assign to pad 0
        app.editor.assign_sample(0, sample, PlaybackMode.ONE_SHOT, Color(r=127, g=0, b=0))

        # Trigger the pad via MIDI event
        midi_event = MidiEvent(
            type="NOTE_ON",
            note=app.launchpad.pads[0].note,
            velocity=127
        )

        # In play mode, MIDI triggers should work
        app.set_mode("play")
        app.player.on_midi_event(midi_event)

        # Verify pad is playing
        pad_id = 0
        assert app.state_machine.is_pad_playing(pad_id)

        # Trigger note off
        midi_off = MidiEvent(
            type="NOTE_OFF",
            note=app.launchpad.pads[0].note,
            velocity=0
        )
        app.player.on_midi_event(midi_off)

        # For ONE_SHOT mode, note off shouldn't stop it immediately
        # (it plays to completion)
        assert app.state_machine.is_pad_playing(pad_id)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_playback_mode_one_shot(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test ONE_SHOT playback mode plays sample to completion."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load sample and assign as ONE_SHOT
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.ONE_SHOT, Color(r=127, g=0, b=0))

        app.set_mode("play")

        # Trigger
        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)

        assert app.state_machine.is_pad_playing(0)

        # Note off shouldn't stop ONE_SHOT
        midi_off = MidiEvent(type="NOTE_OFF", note=app.launchpad.pads[0].note, velocity=0)
        app.player.on_midi_event(midi_off)

        # Still playing
        assert app.state_machine.is_pad_playing(0)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_playback_mode_hold(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test HOLD playback mode stops on note off."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load sample and assign as HOLD
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.HOLD, Color(r=0, g=127, b=0))

        app.set_mode("play")

        # Trigger
        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)

        assert app.state_machine.is_pad_playing(0)

        # Note off should stop HOLD
        midi_off = MidiEvent(type="NOTE_OFF", note=app.launchpad.pads[0].note, velocity=0)
        app.player.on_midi_event(midi_off)

        # Should have stopped
        assert not app.state_machine.is_pad_playing(0)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_playback_mode_loop(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test LOOP playback mode loops until stopped."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load sample and assign as LOOP
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.LOOP, Color(r=0, g=0, b=127))

        app.set_mode("play")

        # Trigger
        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)

        assert app.state_machine.is_pad_playing(0)

        # Note off should stop LOOP
        midi_off = MidiEvent(type="NOTE_OFF", note=app.launchpad.pads[0].note, velocity=0)
        app.player.on_midi_event(midi_off)

        assert not app.state_machine.is_pad_playing(0)


@pytest.mark.integration
class TestMultipleSamplePlayback:
    """Test playing multiple samples simultaneously."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_multiple_pads_play_simultaneously(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that multiple pads can play at the same time."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load sample and assign to multiple pads
        sample = Sample.from_file(sample_audio_file)
        for pad_id in [0, 1, 2]:
            app.editor.assign_sample(
                pad_id, sample, PlaybackMode.ONE_SHOT, Color(r=127, g=0, b=0)
            )

        app.set_mode("play")

        # Trigger all pads
        for pad_id in [0, 1, 2]:
            midi_on = MidiEvent(
                type="NOTE_ON",
                note=app.launchpad.pads[pad_id].note,
                velocity=127
            )
            app.player.on_midi_event(midi_on)

        # All should be playing
        assert app.state_machine.is_pad_playing(0)
        assert app.state_machine.is_pad_playing(1)
        assert app.state_machine.is_pad_playing(2)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_retriggering_pad_restarts_playback(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that retriggering a pad restarts its playback."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Load sample
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.LOOP, Color(r=127, g=0, b=0))

        app.set_mode("play")

        # Trigger once
        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)
        assert app.state_machine.is_pad_playing(0)

        # Trigger again (retrigger)
        app.player.on_midi_event(midi_on)
        assert app.state_machine.is_pad_playing(0)

        # Should still be playing (restarted)
        midi_off = MidiEvent(type="NOTE_OFF", note=app.launchpad.pads[0].note, velocity=0)
        app.player.on_midi_event(midi_off)
        assert not app.state_machine.is_pad_playing(0)


@pytest.mark.integration
class TestModeSwitching:
    """Test switching between edit and play modes."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_switching_to_edit_mode_stops_playback(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that switching to edit mode stops all playback."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, start_mode="play")
        app.initialize()

        # Load and trigger sample
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.LOOP, Color(r=127, g=0, b=0))

        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)
        assert app.state_machine.is_pad_playing(0)

        # Switch to edit mode
        app.set_mode("edit")

        # Playback should have stopped
        assert not app.state_machine.is_pad_playing(0)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_edit_mode_midi_does_not_trigger_playback(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that MIDI events in edit mode don't trigger playback."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, start_mode="edit")
        app.initialize()

        # Load sample
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.ONE_SHOT, Color(r=127, g=0, b=0))

        # Try to trigger in edit mode
        midi_on = MidiEvent(type="NOTE_ON", note=app.launchpad.pads[0].note, velocity=127)
        app.player.on_midi_event(midi_on)

        # Should not be playing (edit mode)
        assert not app.state_machine.is_pad_playing(0)

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_mode_switching_preserves_pad_assignments(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that switching modes doesn't lose pad assignments."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, start_mode="edit")
        app.initialize()

        # Assign sample in edit mode
        sample = Sample.from_file(sample_audio_file)
        app.editor.assign_sample(0, sample, PlaybackMode.ONE_SHOT, Color(r=127, g=0, b=0))

        # Switch to play mode
        app.set_mode("play")

        # Pad should still have the sample
        assert app.launchpad.pads[0].sample is not None
        assert app.launchpad.pads[0].sample.name == sample.name

        # Switch back to edit
        app.set_mode("edit")

        # Still there
        assert app.launchpad.pads[0].sample is not None
        assert app.launchpad.pads[0].sample.name == sample.name
