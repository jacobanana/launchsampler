"""Unit tests for TUIService."""

from unittest.mock import Mock, call

import pytest

from launchsampler.models import Launchpad, Sample
from launchsampler.protocols import AppEvent
from launchsampler.tui.services import TUIService


class TestTUIServiceObserver:
    """Test TUIService as an AppObserver."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock LaunchpadSampler app."""
        app = Mock()
        app.launchpad = Launchpad.create_empty()
        app.editor = Mock()
        app.selected_pad_index = None
        app.player = Mock()
        app.player._engine = None
        return app

    @pytest.fixture
    def service(self, mock_app):
        """Create TUIService instance."""
        return TUIService(mock_app)

    @pytest.mark.unit
    def test_implements_app_observer_protocol(self, service):
        """Test that TUIService implements AppObserver protocol."""
        from launchsampler.protocols import AppObserver

        # Verify protocol method exists
        assert hasattr(service, "on_app_event")
        assert callable(service.on_app_event)

        # Verify it's recognized as an AppObserver at runtime
        assert isinstance(service, AppObserver)

    @pytest.mark.unit
    def test_on_app_event_set_mounted(self, service, mock_app):
        """Test handling SET_MOUNTED event."""
        # Setup mock grid
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call event handler
        service.on_app_event(AppEvent.SET_MOUNTED)

        # Verify grid.update_pad was called for all 64 pads
        assert mock_grid.update_pad.call_count == 64

        # Verify calls were made with correct indices and pads
        calls = mock_grid.update_pad.call_args_list
        for i in range(64):
            assert calls[i] == call(i, mock_app.launchpad.pads[i])

    @pytest.mark.unit
    def test_on_app_event_set_mounted_with_selection(self, service, mock_app, sample_audio_file):
        """Test SET_MOUNTED updates details panel when pad is selected."""
        # Setup: assign sample to pad 5 and select it
        mock_app.launchpad.pads[5].sample = Sample.from_file(sample_audio_file)
        mock_app.selected_pad_index = 5  # Selection now on app, not editor

        # Setup mocks
        mock_grid = Mock()
        mock_details = Mock()

        def query_one_side_effect(widget_type):
            """Return appropriate mock based on widget type."""
            from launchsampler.tui.widgets import PadDetailsPanel, PadGrid

            if widget_type == PadGrid:
                return mock_grid
            elif widget_type == PadDetailsPanel:
                return mock_details
            raise ValueError(f"Unexpected widget type: {widget_type}")

        mock_app.query_one = Mock(side_effect=query_one_side_effect)

        # Call event handler
        service.on_app_event(AppEvent.SET_MOUNTED)

        # Verify grid was updated
        assert mock_grid.update_pad.call_count == 64

        # Verify details panel was updated for selected pad
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[0][0] == 5  # pad_index
        assert call_args[0][1] == mock_app.launchpad.pads[5]  # pad

    @pytest.mark.unit
    def test_on_app_event_set_mounted_no_selection(self, service, mock_app):
        """Test SET_MOUNTED doesn't update details when no pad selected."""
        # Setup: no pad selected
        mock_app.selected_pad_index = None

        # Setup mocks
        mock_grid = Mock()
        mock_details = Mock()

        def query_one_side_effect(widget_type):
            from launchsampler.tui.widgets import PadDetailsPanel, PadGrid

            if widget_type == PadGrid:
                return mock_grid
            elif widget_type == PadDetailsPanel:
                return mock_details
            raise ValueError(f"Unexpected widget type: {widget_type}")

        mock_app.query_one = Mock(side_effect=query_one_side_effect)

        # Call event handler
        service.on_app_event(AppEvent.SET_MOUNTED)

        # Verify grid was updated
        assert mock_grid.update_pad.call_count == 64

        # Verify details panel was NOT updated
        mock_details.update_for_pad.assert_not_called()

    @pytest.mark.unit
    def test_on_app_event_set_saved(self, service):
        """Test handling SET_SAVED event (currently a no-op)."""
        # Should not raise any exception
        service.on_app_event(AppEvent.SET_SAVED, path="/some/path.json")

    @pytest.mark.unit
    def test_on_app_event_mode_changed(self, service):
        """Test handling MODE_CHANGED event (currently a no-op)."""
        # Should not raise any exception
        service.on_app_event(AppEvent.MODE_CHANGED, mode="play")

    @pytest.mark.unit
    def test_on_app_event_unknown_event(self, service, caplog):
        """Test handling unknown event logs warning."""
        # Create a mock event (not a real AppEvent)
        unknown_event = Mock()
        unknown_event.value = "unknown"

        # Call with unknown event
        service.on_app_event(unknown_event)

        # Verify warning was logged
        assert "unknown app event" in caplog.text.lower()

    @pytest.mark.unit
    def test_on_app_event_handles_exceptions(self, service, mock_app, caplog):
        """Test that exceptions in event handlers are caught and logged."""
        # Setup mock that raises exception
        mock_app.query_one = Mock(side_effect=Exception("Test exception"))

        # Call event handler - should not raise
        service.on_app_event(AppEvent.SET_MOUNTED)

        # Verify error was logged (exception occurs in nested method)
        assert "error syncing ui" in caplog.text.lower() or "test exception" in caplog.text.lower()

    @pytest.mark.unit
    def test_update_selected_pad_ui_with_audio_data(self, service, mock_app, sample_audio_file):
        """Test updating selected pad UI includes audio data when available."""
        # Setup: player with audio data
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_audio_data = Mock()
        mock_app.player.get_audio_data = Mock(return_value=mock_audio_data)

        # Setup details panel mock
        mock_details = Mock()
        mock_app.query_one = Mock(return_value=mock_details)

        # Call internal method
        service._update_selected_pad_ui(3, mock_app.launchpad.pads[3])

        # Verify player was queried for audio data
        mock_app.player.get_audio_data.assert_called_once_with(3)

        # Verify details panel was updated with audio data
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[1]["audio_data"] == mock_audio_data

    @pytest.mark.unit
    def test_update_selected_pad_ui_without_engine(self, service, mock_app, sample_audio_file):
        """Test updating selected pad UI when engine is not available."""
        # Setup: player returns None (simulating no engine)
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_app.player.get_audio_data = Mock(return_value=None)

        # Setup details panel mock
        mock_details = Mock()
        mock_app.query_one = Mock(return_value=mock_details)

        # Call internal method
        service._update_selected_pad_ui(3, mock_app.launchpad.pads[3])

        # Verify details panel was updated with None audio data
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[1]["audio_data"] is None

    @pytest.mark.unit
    def test_update_selected_pad_ui_unassigned_pad(self, service, mock_app):
        """Test updating selected pad UI for unassigned pad."""
        # Setup: unassigned pad, player available but shouldn't be queried for audio data
        mock_app.player.get_audio_data = Mock(return_value=None)

        # Setup details panel mock
        mock_details = Mock()
        mock_app.query_one = Mock(return_value=mock_details)

        # Call internal method with unassigned pad
        service._update_selected_pad_ui(7, mock_app.launchpad.pads[7])

        # Verify player was NOT queried (pad not assigned)
        mock_app.player.get_audio_data.assert_not_called()

        # Verify details panel was still updated
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[1]["audio_data"] is None

    @pytest.mark.unit
    def test_update_pad_ui_sets_unavailable_when_no_audio_data(
        self, service, mock_app, sample_audio_file
    ):
        """Test that pad is marked as unavailable when audio data is None."""
        # Setup: assign sample to pad but audio data unavailable
        mock_app.launchpad.pads[5].sample = Sample.from_file(sample_audio_file)
        mock_app.player.get_audio_data = Mock(return_value=None)

        # Setup grid mock
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call internal method
        service._update_pad_ui(5, mock_app.launchpad.pads[5])

        # Verify grid.update_pad was called
        mock_grid.update_pad.assert_called_once_with(5, mock_app.launchpad.pads[5])

        # Verify grid.set_pad_unavailable was called with True
        mock_grid.set_pad_unavailable.assert_called_once_with(5, True)

    @pytest.mark.unit
    def test_update_pad_ui_clears_unavailable_when_audio_data_available(
        self, service, mock_app, sample_audio_file
    ):
        """Test that pad is marked as available when audio data exists."""
        # Setup: assign sample to pad with audio data available
        mock_app.launchpad.pads[5].sample = Sample.from_file(sample_audio_file)
        mock_audio_data = Mock()
        mock_app.player.get_audio_data = Mock(return_value=mock_audio_data)

        # Setup grid mock
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call internal method
        service._update_pad_ui(5, mock_app.launchpad.pads[5])

        # Verify grid.update_pad was called
        mock_grid.update_pad.assert_called_once_with(5, mock_app.launchpad.pads[5])

        # Verify grid.set_pad_unavailable was called with False
        mock_grid.set_pad_unavailable.assert_called_once_with(5, False)

    @pytest.mark.unit
    def test_update_pad_ui_clears_unavailable_for_empty_pad(self, service, mock_app):
        """Test that unavailable state is cleared for empty pads."""
        # Setup: unassigned pad
        mock_app.player.get_audio_data = Mock(return_value=None)

        # Setup grid mock
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call internal method with unassigned pad
        service._update_pad_ui(7, mock_app.launchpad.pads[7])

        # Verify grid.update_pad was called
        mock_grid.update_pad.assert_called_once_with(7, mock_app.launchpad.pads[7])

        # Verify grid.set_pad_unavailable was called with False (clear unavailable)
        mock_grid.set_pad_unavailable.assert_called_once_with(7, False)

    @pytest.mark.unit
    def test_set_mounted_checks_unavailable_for_all_pads(
        self, service, mock_app, sample_audio_file
    ):
        """Test that SET_MOUNTED checks availability for all assigned pads."""
        # Setup: assign samples to some pads, some with audio data, some without
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_app.launchpad.pads[5].sample = Sample.from_file(sample_audio_file)
        mock_app.launchpad.pads[7].sample = Sample.from_file(sample_audio_file)

        # Mock audio data: pad 3 has audio, pad 5 doesn't, pad 7 has audio
        def get_audio_data_side_effect(pad_index):
            if pad_index == 3:
                return Mock()  # Audio data available
            elif pad_index == 5:
                return None  # Audio data unavailable
            elif pad_index == 7:
                return Mock()  # Audio data available
            return None

        mock_app.player.get_audio_data = Mock(side_effect=get_audio_data_side_effect)

        # Setup grid mock
        mock_grid = Mock()
        mock_app.query_one = Mock(return_value=mock_grid)

        # Call event handler
        service.on_app_event(AppEvent.SET_MOUNTED)

        # Verify grid.update_pad was called for all 64 pads
        assert mock_grid.update_pad.call_count == 64

        # Verify grid.set_pad_unavailable was called for all 64 pads
        assert mock_grid.set_pad_unavailable.call_count == 64

        # Verify specific calls for assigned pads
        unavailable_calls = mock_grid.set_pad_unavailable.call_args_list
        assert call(3, False) in unavailable_calls  # Has audio data
        assert call(5, True) in unavailable_calls  # No audio data
        assert call(7, False) in unavailable_calls  # Has audio data

        # Verify unassigned pads are marked as not unavailable
        assert call(0, False) in unavailable_calls  # Empty pad
