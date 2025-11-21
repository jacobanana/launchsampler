"""Smoke tests for TUI using Textual's test framework.

These tests verify that the TUI can launch, render, and respond to basic
interactions without crashing. They don't test detailed behavior, just that
the core functionality works.
"""

from unittest.mock import Mock, patch

import pytest

from launchsampler.models import AppConfig
from launchsampler.orchestration import Orchestrator
from launchsampler.tui import LaunchpadSampler


@pytest.fixture
def config(temp_dir):
    """Create test configuration."""
    return AppConfig(default_audio_device=None, default_buffer_size=256, midi_poll_interval=5.0)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTUILaunch:
    """Test that TUI can launch without crashing."""

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_tui_launches_successfully(self, mock_audio_device, mock_controller, config):
        """Test that TUI application can start and initialize."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        # Create orchestrator (don't initialize yet)
        orchestrator = Orchestrator(config, start_mode="edit")

        # Create TUI
        app = LaunchpadSampler(orchestrator, start_mode="edit")

        # Initialize TUI before running
        app.initialize()

        # Run TUI in test mode
        async with app.run_test():
            # TUI should have started
            assert app.orchestrator is not None
            assert app.tui_service is not None

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_tui_mounts_widgets(self, mock_audio_device, mock_controller, config):
        """Test that TUI mounts all required widgets."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            # Wait for app to mount
            await pilot.pause()

            # Verify key widgets are present
            assert app.query_one("PadGrid") is not None
            assert app.query_one("PadDetailsPanel") is not None
            assert app.query_one("StatusBar") is not None

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_tui_displays_header_footer(self, mock_audio_device, mock_controller, config):
        """Test that TUI displays header and footer."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Check for header and footer
            header = app.query_one("Header")
            footer = app.query_one("Footer")

            assert header is not None
            assert footer is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTUINavigation:
    """Test basic TUI navigation and interaction."""

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_arrow_key_navigation(self, mock_audio_device, mock_controller, config):
        """Test that arrow keys navigate the pad grid."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Start at pad 0
            initial_selection = app._selected_pad_index
            assert initial_selection is not None

            # Press right arrow
            await pilot.press("right")
            await pilot.pause()

            # Selection should have moved
            new_selection = app._selected_pad_index
            assert new_selection != initial_selection

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_pad_grid_renders(self, mock_audio_device, mock_controller, config):
        """Test that pad grid renders with 64 pads."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            pad_grid = app.query_one("PadGrid")
            assert pad_grid is not None

            # Grid should have widgets for all pads
            # (Implementation detail: might be rows × cols structure)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTUIModeSwitching:
    """Test switching between edit and play modes."""

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_switch_to_edit_mode(self, mock_audio_device, mock_controller, config):
        """Test pressing 'e' switches to edit mode."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="play")
        app = LaunchpadSampler(orchestrator, start_mode="play")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Should start in play mode
            assert app.orchestrator.mode == "play"

            # Press 'e' to switch to edit
            await pilot.press("e")
            await pilot.pause()

            # Should now be in edit mode
            assert app.orchestrator.mode == "edit"

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_switch_to_play_mode(self, mock_audio_device, mock_controller, config):
        """Test pressing 'p' switches to play mode."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Should start in edit mode
            assert app.orchestrator.mode == "edit"

            # Press 'p' to switch to play
            await pilot.press("p")
            await pilot.pause()

            # Should now be in play mode
            assert app.orchestrator.mode == "play"

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_mode_indicator_updates(self, mock_audio_device, mock_controller, config):
        """Test that mode indicator updates when switching modes."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Get status bar
            status_bar = app.query_one("StatusBar")
            assert status_bar is not None

            # Switch modes
            await pilot.press("p")
            await pilot.pause()

            # Status bar should reflect new mode
            # (Exact assertion depends on status bar implementation)
            assert app.orchestrator.mode == "play"


@pytest.mark.integration
@pytest.mark.asyncio
class TestTUIKeyBindings:
    """Test critical keybindings work."""

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_quit_keybinding(self, mock_audio_device, mock_controller, config):
        """Test that ctrl+q quits the application."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press ctrl+q to quit
            await pilot.press("ctrl+q")
            await pilot.pause()

            # App should be exiting
            # (run_test context manager handles cleanup)

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_escape_stops_audio(self, mock_audio_device, mock_controller, config):
        """Test that escape key stops all audio (panic button)."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        orchestrator = Orchestrator(config, start_mode="play")
        app = LaunchpadSampler(orchestrator, start_mode="play")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # Press escape (panic)
            await pilot.press("escape")
            await pilot.pause()

            # All playback should be stopped
            # (Exact verification depends on state machine)
            for pad_id in range(64):
                assert not app.orchestrator.state_machine.is_pad_playing(pad_id)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTUIWithSamples:
    """Test TUI with loaded samples."""

    @patch("launchsampler.orchestration.orchestrator.DeviceController")
    @patch("launchsampler.core.player.AudioDevice")
    async def test_tui_displays_loaded_samples(
        self, mock_audio_device, mock_controller, config, sample_audio_file, temp_dir
    ):
        """Test that TUI displays samples when loaded."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_device_instance.start.return_value = True
        mock_audio_device.return_value = mock_device_instance

        # Create a directory with a sample
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()
        import shutil

        shutil.copy(sample_audio_file, samples_dir / "kick.wav")

        # Create orchestrator with samples
        orchestrator = Orchestrator(config, samples_dir=samples_dir, start_mode="edit")
        app = LaunchpadSampler(orchestrator, start_mode="edit")
        app.initialize()

        async with app.run_test() as pilot:
            await pilot.pause()

            # First pad should have the sample
            assert app.orchestrator.launchpad.pads[0].sample is not None

            # Pad details should show the sample info
            pad_details = app.query_one("PadDetailsPanel")
            assert pad_details is not None
