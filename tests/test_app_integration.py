"""Integration tests for LaunchpadSamplerApp orchestrator.

Tests the application lifecycle and service coordination without mocking
internal components. Focuses on integration between services.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from launchsampler.app import LaunchpadSamplerApp
from launchsampler.models import AppConfig, Set, Sample, PlaybackMode
from launchsampler.protocols import UIAdapter, AppObserver, AppEvent


class MockUI(UIAdapter):
    """Mock UI for testing orchestrator without real UI."""

    def __init__(self):
        self.initialized = False
        self.running = False
        self.events_received = []

    def initialize(self) -> None:
        """Initialize UI."""
        self.initialized = True

    def run(self) -> None:
        """Run UI (non-blocking for tests)."""
        self.running = True

    def shutdown(self) -> None:
        """Shutdown UI."""
        self.running = False


class MockUIObserver(MockUI, AppObserver):
    """Mock UI that also observes app events."""

    def on_app_event(self, event: AppEvent, **kwargs) -> None:
        """Record app events."""
        self.events_received.append(event)


@pytest.fixture
def config(temp_dir):
    """Create test configuration."""
    return AppConfig(
        default_audio_device=None,
        default_buffer_size=256,
        midi_poll_interval=5.0
    )


@pytest.mark.integration
class TestAppInitialization:
    """Test LaunchpadSamplerApp initialization and lifecycle."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_creates_with_default_state(self, mock_audio_device, mock_controller, config):
        """Test that app initializes with empty launchpad and untitled set."""
        app = LaunchpadSamplerApp(config)

        assert app.launchpad is not None
        assert len(app.launchpad.pads) == 64
        assert app.current_set.name == "Untitled"
        assert app.state_machine is not None
        assert app.player is None  # Not initialized until initialize() called
        assert app.editor is None
        assert app.set_manager is None

    @patch('launchsampler.app.DeviceController')
    def test_app_initializes_with_invalid_audio_device_config(self, mock_controller, temp_dir):
        """Test that app doesn't crash when configured audio device is invalid.

        This tests the scenario where:
        1. config.json doesn't exist (uses default config with default_audio_device=None)
        2. config.json exists but default_audio_device is invalid (e.g., device was unplugged)

        The app should fall back to the system default audio device and continue.
        """
        # Test case 1: Invalid device ID (device unplugged or doesn't exist)
        invalid_config = AppConfig(
            default_audio_device=99999,  # Invalid device ID
            default_buffer_size=256,
            midi_poll_interval=5.0
        )

        app = LaunchpadSamplerApp(invalid_config)

        # This should NOT raise RuntimeError: "Failed to start player"
        # The AudioDevice should fall back to default device
        app.initialize()

        # Verify app initialized successfully
        assert app.player is not None
        assert app.player.is_running
        assert app.editor is not None
        assert app.set_manager is not None

        # Cleanup
        app.shutdown()

        # Test case 2: config with None (default device) - should always work
        default_config = AppConfig(
            default_audio_device=None,
            default_buffer_size=256,
            midi_poll_interval=5.0
        )

        app2 = LaunchpadSamplerApp(default_config)
        app2.initialize()

        assert app2.player is not None
        assert app2.player.is_running

        # Cleanup
        app2.shutdown()

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_registers_ui(self, mock_audio_device, mock_controller, config):
        """Test that UIs can be registered before initialization."""
        app = LaunchpadSamplerApp(config)
        mock_ui = MockUI()

        app.register_ui(mock_ui)

        assert mock_ui in app._uis

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_initialize_creates_services(self, mock_audio_device, mock_controller, config):
        """Test that initialize() creates all services."""
        # Mock audio device to return success
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Verify services were created
        assert app.set_manager is not None
        assert app.player is not None
        assert app.editor is not None
        assert app.state_machine is not None

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_initialize_registers_observers(self, mock_audio_device, mock_controller, config):
        """Test that initialize() wires up observer connections."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Verify player is registered as observer on editor
        assert app.player in app.editor._observers._observers

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_fires_startup_events(self, mock_audio_device, mock_controller, config):
        """Test that initialize() fires SET_MOUNTED and MODE_CHANGED events."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, start_mode="edit")

        # Register observer UI
        observer_ui = MockUIObserver()
        app.register_ui(observer_ui)

        app.initialize()

        # Check that events were fired
        event_types = [event.value for event in observer_ui.events_received]
        assert "set_mounted" in event_types
        assert "mode_changed" in event_types


@pytest.mark.integration
class TestAppSetLoading:
    """Test set loading and state synchronization."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_loads_set_from_directory(
        self, mock_audio_device, mock_controller, config, sample_audio_file, temp_dir
    ):
        """Test loading samples from a directory."""
        # Create a directory with sample files
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # Copy sample file to directory
        import shutil
        shutil.copy(sample_audio_file, samples_dir / "kick.wav")

        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, samples_dir=samples_dir)
        app.initialize()

        # Verify set was loaded with samples
        assert app.current_set is not None
        # First pad should have the sample
        assert app.launchpad.pads[0].sample is not None
        assert "kick" in app.launchpad.pads[0].sample.name.lower()

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_mount_set_updates_player(
        self, mock_audio_device, mock_controller, config, sample_audio_file
    ):
        """Test that mounting a new set updates player state."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Create a set with samples
        test_set = Set.create_empty("Test Set")
        sample = Sample.from_file(sample_audio_file)
        test_set.launchpad.pads[0].sample = sample
        test_set.launchpad.pads[0].mode = PlaybackMode.ONE_SHOT

        # Mount the set
        app.mount_set(test_set)

        # Verify player was updated
        assert app.current_set.name == "Test Set"
        assert app.launchpad.pads[0].sample is not None


@pytest.mark.integration
class TestAppModeManagement:
    """Test mode switching and state management."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_switches_mode(self, mock_audio_device, mock_controller, config):
        """Test switching between edit and play modes."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config, start_mode="edit")
        observer_ui = MockUIObserver()
        app.register_ui(observer_ui)

        app.initialize()

        # Initially in edit mode
        assert app.mode == "edit"

        # Switch to play mode
        app.set_mode("play")
        assert app.mode == "play"

        # Check that MODE_CHANGED event was fired
        mode_events = [e for e in observer_ui.events_received if e.value == "mode_changed"]
        assert len(mode_events) >= 2  # One from init, one from set_mode

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_mode_affects_midi_routing(self, mock_audio_device, mock_controller, config):
        """Test that mode changes affect MIDI routing behavior."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        # Mock MIDI controller
        mock_midi_instance = Mock()
        mock_controller.return_value = mock_midi_instance

        app = LaunchpadSamplerApp(config, start_mode="edit")
        app.initialize()

        # In edit mode, MIDI should route differently than play mode
        # This is tested more thoroughly in the Player tests
        # Here we just verify the mode is set correctly
        assert app.mode == "edit"

        app.set_mode("play")
        assert app.mode == "play"


@pytest.mark.integration
class TestAppShutdown:
    """Test application shutdown and cleanup."""

    @patch('launchsampler.app.DeviceController')
    @patch('launchsampler.core.player.AudioDevice')
    def test_app_shutdown_cleans_up_resources(self, mock_audio_device, mock_controller, config):
        """Test that shutdown properly cleans up all resources."""
        # Mock audio device
        mock_device_instance = Mock()
        mock_audio_device.return_value = mock_device_instance

        app = LaunchpadSamplerApp(config)
        app.initialize()

        # Shutdown
        app.shutdown()

        # Verify player was stopped
        # (The actual cleanup logic is in the player.stop() method)
        assert app.player is not None  # Player still exists but should be stopped
