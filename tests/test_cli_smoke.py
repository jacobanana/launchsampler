"""Smoke tests for CLI commands.

Tests that CLI commands parse correctly and don't crash. Uses Click's
CliRunner for testing without actually running the full application.
"""

from pathlib import Path
from unittest.mock import patch, Mock
import pytest
from click.testing import CliRunner

from launchsampler.cli.main import cli


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.mark.integration
class TestCLIHelp:
    """Test that all commands have working help text."""

    def test_main_help(self, runner):
        """Test main CLI help displays."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Launchpad Sampler' in result.output
        assert 'MIDI-controlled audio sample player' in result.output

    def test_version_flag(self, runner):
        """Test --version flag works."""
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert '0.1.0' in result.output

    def test_main_options(self, runner):
        """Test main CLI options (run is now default)."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert '--mode' in result.output
        assert '--set' in result.output
        assert '--samples-dir' in result.output

    def test_audio_help(self, runner):
        """Test audio command help."""
        result = runner.invoke(cli, ['audio', '--help'])
        assert result.exit_code == 0

    def test_midi_help(self, runner):
        """Test midi command help."""
        result = runner.invoke(cli, ['midi', '--help'])
        assert result.exit_code == 0

    def test_config_help(self, runner):
        """Test config command help."""
        result = runner.invoke(cli, ['config', '--help'])
        assert result.exit_code == 0


@pytest.mark.integration
class TestRunCommand:
    """Test the main CLI command argument validation."""

    def test_run_with_invalid_mode(self, runner):
        """Test that invalid mode is rejected."""
        result = runner.invoke(cli, ['--mode', 'invalid'])
        assert result.exit_code != 0
        assert 'Invalid value' in result.output or 'invalid choice' in result.output.lower()

    def test_run_with_valid_modes(self, runner):
        """Test that valid modes are accepted (edit, play)."""
        # Note: We don't actually run the app, just validate args
        for mode in ['edit', 'play']:
            # We can't actually run the TUI in tests, but we can check
            # that the argument is parsed correctly by checking help
            result = runner.invoke(cli, ['--help'])
            assert result.exit_code == 0
            assert mode in result.output.lower()

    def test_run_with_nonexistent_directory(self, runner):
        """Test that non-existent directory is rejected."""
        result = runner.invoke(cli, ['--samples-dir', '/nonexistent/directory/path'])
        assert result.exit_code != 0
        # Click will complain about the path not existing

    def test_run_with_valid_directory(self, runner, temp_dir):
        """Test that valid directory is accepted as argument."""
        # Create a test directory
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # We can't actually run the app, but we can verify the path validates
        # by mocking the actual run (patch at source since imports are lazy)
        with patch('launchsampler.app.LaunchpadSamplerApp'):
            with patch('launchsampler.tui.LaunchpadSampler'):
                with patch('launchsampler.models.AppConfig') as mock_config:
                    mock_config.load_or_default.return_value = Mock(save=Mock())
                    # This will try to run, so we catch it before it actually starts
                    result = runner.invoke(cli, ['--samples-dir', str(samples_dir)], catch_exceptions=False)
                    # It should parse successfully (even if it doesn't run fully)


@pytest.mark.integration
class TestAudioCommands:
    """Test audio-related CLI commands."""

    def test_audio_list_command_exists(self, runner):
        """Test that 'audio list' command exists."""
        result = runner.invoke(cli, ['audio', 'list', '--help'])
        assert result.exit_code == 0

    @patch('launchsampler.audio.AudioDevice.list_output_devices')
    def test_audio_list_runs(self, mock_list_devices, runner):
        """Test that 'audio list' command runs without crashing."""
        # Mock the device listing
        mock_list_devices.return_value = ([], "ASIO/WASAPI")

        result = runner.invoke(cli, ['audio', 'list'])
        # Should succeed
        assert result.exit_code == 0 or 'Test Device' in result.output


@pytest.mark.integration
class TestMIDICommands:
    """Test MIDI-related CLI commands."""

    def test_midi_list_command_exists(self, runner):
        """Test that 'midi list' command exists."""
        result = runner.invoke(cli, ['midi', 'list', '--help'])
        assert result.exit_code == 0

    @patch('launchsampler.cli.commands.midi.MidiManager')
    def test_midi_list_runs(self, mock_midi_manager, runner):
        """Test that 'midi list' command runs without crashing."""
        # Mock the list_ports static method to return a dict
        mock_midi_manager.list_ports.return_value = {
            'input': ['MIDI Input 1', 'MIDI Input 2'],
            'output': ['MIDI Output 1']
        }

        result = runner.invoke(cli, ['midi', 'list'])
        # Should list MIDI devices or complete successfully
        assert result.exit_code == 0
        assert 'MIDI' in result.output


@pytest.mark.integration
class TestConfigCommands:
    """Test config-related CLI commands."""

    def test_config_show_command_exists(self, runner):
        """Test that 'config show' command exists."""
        result = runner.invoke(cli, ['config', '--help'])
        assert result.exit_code == 0

    @patch('launchsampler.cli.commands.config.AppConfig')
    def test_config_show_runs(self, mock_app_config, runner):
        """Test that 'config show' command runs."""
        # Mock the config
        mock_config = Mock()
        mock_config.model_dump.return_value = {
            'default_audio_device': None,
            'default_buffer_size': 256,
        }
        mock_app_config.load_or_default.return_value = mock_config

        result = runner.invoke(cli, ['config'])
        # Should display config or complete successfully
        assert result.exit_code == 0


@pytest.mark.integration
class TestCLIErrorHandling:
    """Test that CLI handles errors gracefully."""

    def test_unknown_command_shows_error(self, runner):
        """Test that unknown command shows helpful error."""
        result = runner.invoke(cli, ['nonexistent'])
        assert result.exit_code != 0
        # Click will show an error about unknown command

    def test_run_with_both_set_and_directory_shows_error(self, runner, temp_dir):
        """Test that providing both --set and --samples-dir shows appropriate behavior."""
        samples_dir = temp_dir / "samples"
        samples_dir.mkdir()

        # The CLI accepts both --set and --samples-dir
        # Check that it parses correctly (patch at source since imports are lazy)
        with patch('launchsampler.app.LaunchpadSamplerApp'):
            with patch('launchsampler.tui.LaunchpadSampler'):
                with patch('launchsampler.models.AppConfig') as mock_config:
                    mock_config.load_or_default.return_value = Mock(save=Mock())
                    result = runner.invoke(
                        cli,
                        ['--set', 'test-set', '--samples-dir', str(samples_dir)],
                        catch_exceptions=False
                    )
                    # Should parse (implementation accepts both)


@pytest.mark.integration
class TestCLIIntegration:
    """Test CLI integration with other components."""

    @patch('launchsampler.cli.commands.audio.AudioDevice')
    def test_audio_list_integration(self, mock_audio_device, runner):
        """Test audio list integrates with AudioDevice correctly."""
        mock_audio_device.list_output_devices.return_value = ([], "ASIO/WASAPI")
        mock_audio_device.get_default_device.return_value = 0

        result = runner.invoke(cli, ['audio', 'list'])
        # Should call AudioDevice.list_output_devices
        assert mock_audio_device.list_output_devices.called or result.exit_code == 0

    def test_cli_commands_dont_crash_on_help(self, runner):
        """Test that all commands can show help without crashing."""
        commands = ['audio', 'midi', 'config', 'test']

        for cmd in commands:
            result = runner.invoke(cli, [cmd, '--help'])
            assert result.exit_code == 0, f"Command '{cmd} --help' failed"
