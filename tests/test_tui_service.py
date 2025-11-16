"""Unit tests for TUIService."""

from unittest.mock import Mock, MagicMock, call
import pytest

from launchsampler.models import Launchpad, Pad, Sample
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
            from launchsampler.tui.widgets import PadGrid, PadDetailsPanel
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
            from launchsampler.tui.widgets import PadGrid, PadDetailsPanel
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
        # Setup: engine with audio data
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_engine = Mock()
        mock_audio_data = Mock()
        mock_engine.get_audio_data = Mock(return_value=mock_audio_data)
        mock_app.player._engine = mock_engine

        # Setup details panel mock
        mock_details = Mock()
        mock_app.query_one = Mock(return_value=mock_details)

        # Call internal method
        service._update_selected_pad_ui(3, mock_app.launchpad.pads[3])

        # Verify engine was queried for audio data
        mock_engine.get_audio_data.assert_called_once_with(3)

        # Verify details panel was updated with audio data
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[1]["audio_data"] == mock_audio_data

    @pytest.mark.unit
    def test_update_selected_pad_ui_without_engine(self, service, mock_app, sample_audio_file):
        """Test updating selected pad UI when engine is not available."""
        # Setup: no engine
        mock_app.launchpad.pads[3].sample = Sample.from_file(sample_audio_file)
        mock_app.player._engine = None

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
        # Setup: unassigned pad, engine available but shouldn't be queried
        mock_engine = Mock()
        mock_app.player._engine = mock_engine

        # Setup details panel mock
        mock_details = Mock()
        mock_app.query_one = Mock(return_value=mock_details)

        # Call internal method with unassigned pad
        service._update_selected_pad_ui(7, mock_app.launchpad.pads[7])

        # Verify engine was NOT queried (pad not assigned)
        mock_engine.get_audio_data.assert_not_called()

        # Verify details panel was still updated
        mock_details.update_for_pad.assert_called_once()
        call_args = mock_details.update_for_pad.call_args
        assert call_args[1]["audio_data"] is None
