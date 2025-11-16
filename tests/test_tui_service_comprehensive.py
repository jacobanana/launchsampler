"""Comprehensive unit tests for TUIService observer protocols."""

from unittest.mock import Mock, call
import pytest

from launchsampler.models import Launchpad, Sample
from launchsampler.protocols import EditEvent, MidiEvent, PlaybackEvent
from launchsampler.tui.services import TUIService


class TestTUIServiceEditObserver:
    """Test TUIService as an EditObserver."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock LaunchpadSampler app."""
        app = Mock()
        app.launchpad = Launchpad.create_empty()
        app.editor = Mock()
        app.selected_pad_index = 5
        app.player = Mock()
        app.player._engine = None
        return app

    @pytest.fixture
    def service(self, mock_app):
        """Create TUIService instance."""
        return TUIService(mock_app)

    @pytest.mark.unit
    def test_implements_edit_observer_protocol(self, service):
        """Test that TUIService implements EditObserver protocol."""
        from launchsampler.protocols import EditObserver

        assert hasattr(service, "on_edit_event")
        assert callable(service.on_edit_event)
        assert isinstance(service, EditObserver)

    # NOTE: test_on_edit_event_pad_selected removed - PAD_SELECTED no longer exists
    # Selection events now handled via SelectionEvent protocol, not EditEvent

    @pytest.mark.unit
    def test_on_edit_event_pad_assigned(self, service, mock_app, sample_audio_file):
        """Test handling PAD_ASSIGNED event."""
        # Setup
        mock_app.launchpad.pads[7].sample = Sample.from_file(sample_audio_file)
        mock_app.selected_pad_index = 7
        mock_grid = Mock()
        mock_details = Mock()

        def query_one_side_effect(widget_type):
            from launchsampler.tui.widgets import PadGrid, PadDetailsPanel
            if widget_type == PadGrid:
                return mock_grid
            elif widget_type == PadDetailsPanel:
                return mock_details

        mock_app.query_one = Mock(side_effect=query_one_side_effect)

        # Call event handler
        service.on_edit_event(
            EditEvent.PAD_ASSIGNED,
            pad_indices=[7],
            pads=[mock_app.launchpad.pads[7]]
        )

        # Verify grid was updated
        mock_grid.update_pad.assert_called_once_with(7, mock_app.launchpad.pads[7])

        # Verify details panel was updated (because pad 7 is selected)
        mock_details.update_for_pad.assert_called_once()

    @pytest.mark.unit
    def test_on_edit_event_handles_exceptions(self, service, mock_app, caplog):
        """Test that exceptions in edit event handlers are caught and logged."""
        # Setup mock that raises exception
        mock_app.query_one = Mock(side_effect=Exception("Test exception"))

        # Call event handler - should not raise
        service.on_edit_event(
            EditEvent.PAD_CLEARED,
            pad_indices=[0],
            pads=[mock_app.launchpad.pads[0]]
        )

        # Verify error was logged
        assert "error handling edit event" in caplog.text.lower() or "test exception" in caplog.text.lower()


class TestTUIServiceMidiObserver:
    """Test TUIService as a MidiObserver."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock LaunchpadSampler app."""
        app = Mock()
        app.launchpad = Launchpad.create_empty()
        app.call_from_thread = Mock()  # Mock thread dispatcher
        app._sampler_mode = "play"
        app.player = Mock()
        app.player.is_midi_connected = True
        app.player.active_voices = 3
        app.player.audio_device_name = "Test Audio"
        app.player.midi_device_name = "Launchpad X"
        return app

    @pytest.fixture
    def service(self, mock_app):
        """Create TUIService instance."""
        return TUIService(mock_app)

    @pytest.mark.unit
    def test_implements_midi_observer_protocol(self, service):
        """Test that TUIService implements MidiObserver protocol."""
        from launchsampler.protocols import MidiObserver

        assert hasattr(service, "on_midi_event")
        assert callable(service.on_midi_event)
        assert isinstance(service, MidiObserver)

    @pytest.mark.unit
    def test_on_midi_event_note_on(self, service, mock_app):
        """Test handling NOTE_ON event."""
        # Call event handler
        service.on_midi_event(MidiEvent.NOTE_ON, pad_index=5)

        # Verify call_from_thread was used with correct method
        assert mock_app.call_from_thread.call_count == 1
        call_args = mock_app.call_from_thread.call_args
        assert call_args[0][0] == service._set_pad_midi_on_ui
        assert call_args[0][1] == 5
        assert call_args[0][2] is True

    @pytest.mark.unit
    def test_on_midi_event_note_off(self, service, mock_app):
        """Test handling NOTE_OFF event."""
        # Call event handler
        service.on_midi_event(MidiEvent.NOTE_OFF, pad_index=5)

        # Verify call_from_thread was used with correct method
        assert mock_app.call_from_thread.call_count == 1
        call_args = mock_app.call_from_thread.call_args
        assert call_args[0][0] == service._set_pad_midi_on_ui
        assert call_args[0][1] == 5
        assert call_args[0][2] is False

    @pytest.mark.unit
    def test_on_midi_event_controller_connected(self, service, mock_app):
        """Test handling CONTROLLER_CONNECTED event."""
        # Call event handler
        service.on_midi_event(MidiEvent.CONTROLLER_CONNECTED, pad_index=-1)

        # Verify status bar update was scheduled
        assert mock_app.call_from_thread.call_count == 1
        call_args = mock_app.call_from_thread.call_args
        assert call_args[0][0] == service._update_status_bar


class TestTUIServiceStateObserver:
    """Test TUIService as a StateObserver (playback events)."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock LaunchpadSampler app."""
        app = Mock()
        app.launchpad = Launchpad.create_empty()
        app.call_from_thread = Mock()  # Mock thread dispatcher
        app._sampler_mode = "play"
        app.player = Mock()
        app.player.is_midi_connected = True
        app.player.active_voices = 3
        app.player.audio_device_name = "Test Audio"
        app.player.midi_device_name = "Launchpad X"
        return app

    @pytest.fixture
    def service(self, mock_app):
        """Create TUIService instance."""
        return TUIService(mock_app)

    @pytest.mark.unit
    def test_implements_state_observer_protocol(self, service):
        """Test that TUIService implements StateObserver protocol."""
        from launchsampler.protocols import StateObserver

        assert hasattr(service, "on_playback_event")
        assert callable(service.on_playback_event)
        assert isinstance(service, StateObserver)

    @pytest.mark.unit
    def test_on_playback_event_pad_playing(self, service, mock_app):
        """Test handling PAD_PLAYING event."""
        # Call event handler
        service.on_playback_event(PlaybackEvent.PAD_PLAYING, pad_index=10)

        # Verify two calls to call_from_thread (set playing UI + update status bar)
        assert mock_app.call_from_thread.call_count == 2

        # First call should be to set pad playing UI
        first_call = mock_app.call_from_thread.call_args_list[0]
        assert first_call[0][0] == service._set_pad_playing_ui
        assert first_call[0][1] == 10
        assert first_call[0][2] is True

        # Second call should be to update status bar
        second_call = mock_app.call_from_thread.call_args_list[1]
        assert second_call[0][0] == service._update_status_bar

    @pytest.mark.unit
    def test_on_playback_event_pad_stopped(self, service, mock_app):
        """Test handling PAD_STOPPED event."""
        # Call event handler
        service.on_playback_event(PlaybackEvent.PAD_STOPPED, pad_index=10)

        # Verify two calls to call_from_thread
        assert mock_app.call_from_thread.call_count == 2

        # First call should be to set pad playing UI (False)
        first_call = mock_app.call_from_thread.call_args_list[0]
        assert first_call[0][0] == service._set_pad_playing_ui
        assert first_call[0][1] == 10
        assert first_call[0][2] is False

    @pytest.mark.unit
    def test_on_playback_event_pad_finished(self, service, mock_app):
        """Test handling PAD_FINISHED event."""
        # Call event handler
        service.on_playback_event(PlaybackEvent.PAD_FINISHED, pad_index=10)

        # Verify two calls to call_from_thread
        assert mock_app.call_from_thread.call_count == 2

        # First call should be to set pad playing UI (False)
        first_call = mock_app.call_from_thread.call_args_list[0]
        assert first_call[0][2] is False

    @pytest.mark.unit
    def test_on_playback_event_pad_triggered_no_ui_update(self, service, mock_app):
        """Test PAD_TRIGGERED event doesn't trigger UI updates."""
        # Call event handler
        service.on_playback_event(PlaybackEvent.PAD_TRIGGERED, pad_index=10)

        # Verify NO calls to call_from_thread
        mock_app.call_from_thread.assert_not_called()


class TestTUIServiceUIHelpers:
    """Test TUIService UI update helper methods."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock LaunchpadSampler app."""
        app = Mock()
        app.launchpad = Launchpad.create_empty()
        app.editor = Mock()
        app.selected_pad_index = None
        app.player = Mock()
        app.player._engine = None
        app._sampler_mode = "edit"
        app.player.active_voices = 0
        app.player.audio_device_name = "Default"

        # Mock orchestrator with MIDI controller
        app.orchestrator = Mock()
        app.orchestrator.midi_controller = Mock()
        app.orchestrator.midi_controller.is_connected = False
        app.orchestrator.midi_controller.device_name = None

        return app

    @pytest.fixture
    def service(self, mock_app):
        """Create TUIService instance."""
        return TUIService(mock_app)

    @pytest.mark.unit
    def test_update_status_bar(self, service, mock_app):
        """Test updating status bar."""
        mock_status = Mock()
        mock_app.query_one = Mock(return_value=mock_status)

        # Call method
        service._update_status_bar()

        # Verify status bar was updated with MIDI status from orchestrator
        mock_status.update_state.assert_called_once_with(
            mode="edit",
            connected=False,
            voices=0,
            audio_device="Default",
            midi_device=None
        )

    @pytest.mark.unit
    def test_set_pad_playing_ui(self, service, mock_app):
        """Test setting pad playing state."""
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call method
        service._set_pad_playing_ui(15, True)

        # Verify grid was updated
        mock_grid.set_pad_playing.assert_called_once_with(15, True)

    @pytest.mark.unit
    def test_set_pad_midi_on_ui(self, service, mock_app):
        """Test setting pad MIDI on state."""
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call method
        service._set_pad_midi_on_ui(20, True)

        # Verify grid was updated
        mock_grid.set_pad_midi_on.assert_called_once_with(20, True)

    @pytest.mark.unit
    def test_update_pad_ui_not_selected(self, service, mock_app, sample_audio_file):
        """Test updating pad UI when pad is NOT selected."""
        # Setup
        mock_app.launchpad.pads[10].sample = Sample.from_file(sample_audio_file)
        mock_app.selected_pad_index = 5  # Different pad selected
        mock_grid = Mock()
        mock_details = Mock()

        def query_one_side_effect(widget_type):
            from launchsampler.tui.widgets import PadGrid, PadDetailsPanel
            if widget_type == PadGrid:
                return mock_grid
            elif widget_type == PadDetailsPanel:
                return mock_details

        mock_app.query_one = Mock(side_effect=query_one_side_effect)

        # Call method
        service._update_pad_ui(10, mock_app.launchpad.pads[10])

        # Verify grid was updated
        mock_grid.update_pad.assert_called_once_with(10, mock_app.launchpad.pads[10])

        # Verify details panel was NOT updated (different pad selected)
        mock_details.update_for_pad.assert_not_called()

    @pytest.mark.unit
    def test_update_selected_pad_ui_with_grid(self, service, mock_app, sample_audio_file):
        """Test _update_selected_pad_ui updates both grid and details."""
        # Setup
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_grid = Mock()
        mock_details = Mock()

        def query_one_side_effect(widget_type):
            from launchsampler.tui.widgets import PadGrid, PadDetailsPanel
            if widget_type == PadGrid:
                return mock_grid
            elif widget_type == PadDetailsPanel:
                return mock_details

        mock_app.query_one = Mock(side_effect=query_one_side_effect)

        # Call method
        service._update_selected_pad_ui(3, mock_app.launchpad.pads[3])

        # Verify grid selection was updated
        mock_grid.select_pad.assert_called_once_with(3)

        # Verify details panel was updated
        mock_details.update_for_pad.assert_called_once()
