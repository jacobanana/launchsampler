"""Tests for the state machine and event system."""

import unittest
from unittest.mock import Mock

from launchsampler.core.state_machine import SamplerStateMachine
from launchsampler.protocols import PlaybackEvent, StateObserver


class TestSamplerStateMachine(unittest.TestCase):
    """Test state machine functionality."""

    def test_create_state_machine(self):
        """Test creating a state machine."""
        machine = SamplerStateMachine()
        assert machine is not None
        assert machine.get_playing_pads() == []

    def test_register_observer(self):
        """Test registering an observer."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)

        machine.register_observer(observer)
        # Should not raise

    def test_unregister_observer(self):
        """Test unregistering an observer."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)

        machine.register_observer(observer)
        machine.unregister_observer(observer)
        # Should not raise

    def test_pad_triggered_event(self):
        """Test pad triggered event."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        machine.notify_pad_triggered(5)

        observer.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_TRIGGERED, 5)

    def test_pad_playing_event(self):
        """Test pad playing event."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        machine.notify_pad_playing(10)

        assert machine.is_pad_playing(10)
        observer.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_PLAYING, 10)

    def test_pad_stopped_event(self):
        """Test pad stopped event."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        # Start playing first
        machine.notify_pad_playing(15)
        observer.on_playback_event.reset_mock()

        # Then stop
        machine.notify_pad_stopped(15)

        assert not machine.is_pad_playing(15)
        observer.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_STOPPED, 15)

    def test_pad_finished_event(self):
        """Test pad finished event."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        # Start playing first
        machine.notify_pad_playing(20)
        observer.on_playback_event.reset_mock()

        # Then finish
        machine.notify_pad_finished(20)

        assert not machine.is_pad_playing(20)
        observer.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_FINISHED, 20)

    def test_get_playing_pads(self):
        """Test getting list of playing pads."""
        machine = SamplerStateMachine()

        # Initially empty
        assert machine.get_playing_pads() == []

        # Start some pads
        machine.notify_pad_playing(0)
        machine.notify_pad_playing(5)
        machine.notify_pad_playing(10)

        playing = machine.get_playing_pads()
        assert len(playing) == 3
        assert 0 in playing
        assert 5 in playing
        assert 10 in playing

        # Stop one
        machine.notify_pad_stopped(5)
        playing = machine.get_playing_pads()
        assert len(playing) == 2
        assert 0 in playing
        assert 10 in playing
        assert 5 not in playing

    def test_multiple_observers(self):
        """Test that multiple observers all receive events."""
        machine = SamplerStateMachine()
        observer1 = Mock(spec=StateObserver)
        observer2 = Mock(spec=StateObserver)

        machine.register_observer(observer1)
        machine.register_observer(observer2)

        machine.notify_pad_triggered(3)

        observer1.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_TRIGGERED, 3)
        observer2.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_TRIGGERED, 3)

    def test_observer_exception_doesnt_break_others(self):
        """Test that if one observer raises an exception, others still get called."""
        machine = SamplerStateMachine()

        # Observer that raises exception
        bad_observer = Mock(spec=StateObserver)
        bad_observer.on_playback_event.side_effect = RuntimeError("Bad observer")

        # Good observer
        good_observer = Mock(spec=StateObserver)

        machine.register_observer(bad_observer)
        machine.register_observer(good_observer)

        # Should not raise
        machine.notify_pad_triggered(7)

        # Both should have been called
        bad_observer.on_playback_event.assert_called_once()
        good_observer.on_playback_event.assert_called_once_with(PlaybackEvent.PAD_TRIGGERED, 7)

    def test_stop_pad_not_playing_doesnt_notify(self):
        """Test that stopping a pad that's not playing doesn't send event."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        # Try to stop a pad that was never started
        machine.notify_pad_stopped(25)

        # Should not notify since it wasn't playing
        observer.on_playback_event.assert_not_called()

    def test_trigger_then_playing_workflow(self):
        """Test the typical workflow: trigger -> playing -> finished."""
        machine = SamplerStateMachine()
        observer = Mock(spec=StateObserver)
        machine.register_observer(observer)

        # Trigger
        machine.notify_pad_triggered(1)
        assert not machine.is_pad_playing(1)  # Not playing yet, just triggered
        assert observer.on_playback_event.call_count == 1

        # Start playing
        machine.notify_pad_playing(1)
        assert machine.is_pad_playing(1)
        assert observer.on_playback_event.call_count == 2

        # Finish
        machine.notify_pad_finished(1)
        assert not machine.is_pad_playing(1)
        assert observer.on_playback_event.call_count == 3

        # Verify all events were sent in order
        calls = observer.on_playback_event.call_args_list
        assert calls[0][0] == (PlaybackEvent.PAD_TRIGGERED, 1)
        assert calls[1][0] == (PlaybackEvent.PAD_PLAYING, 1)
        assert calls[2][0] == (PlaybackEvent.PAD_FINISHED, 1)


if __name__ == '__main__':
    unittest.main()
