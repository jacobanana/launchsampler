"""Main CLI entry point."""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

import click

from .commands import audio_group, midi_group, config, test

logger = logging.getLogger(__name__)


def setup_logging(verbose: int, debug: bool, log_file: Optional[Path], log_level: str) -> None:
    """
    Configure logging for the application.

    Args:
        verbose: Verbosity count (0 = WARNING, 1 = INFO, 2+ = DEBUG)
        debug: If True, enable debug mode with file logging
        log_file: Custom log file path (optional)
        log_level: Log level for file logging (DEBUG/INFO/WARNING/ERROR)
    """
    # Determine log level based on flags
    if debug:
        level = logging.DEBUG
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    # Override with explicit log level if provided
    if log_file:
        level = getattr(logging, log_level.upper())

    # Determine log file path
    if debug and not log_file:
        # Debug mode: log to current directory
        log_path = Path.cwd() / "launchsampler-debug.log"
    elif log_file:
        # Custom log file specified
        log_path = log_file
    else:
        # Default: log to launchsampler directory
        config_dir = Path.home() / ".launchsampler" / "logs"
        config_dir.mkdir(parents=True, exist_ok=True)
        log_path = config_dir / "launchsampler.log"

    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create rotating file handler (keeps last 5 files, max 10MB each)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)

    # Log the configuration
    logger.info(f"Logging configured: level={logging.getLevelName(level)}, file={log_path}")


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0", prog_name="launchsampler")
@click.option(
    '--set',
    '-s',
    type=str,
    default=None,
    help='Name of saved set to load (from config/sets/)'
)
@click.option(
    '--mode',
    '-m',
    type=click.Choice(['edit', 'play'], case_sensitive=False),
    default='play',
    help='Start in edit or play mode (default: play)'
)
@click.option(
    '--led-ui/--no-led-ui',
    default=True,
    help='Enable LED UI on Launchpad hardware (default: enabled)'
)
@click.option(
    '--samples-dir',
    '-d',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help='Load samples from directory'
)
@click.option(
    '-v', '--verbose',
    count=True,
    help='Increase verbosity (-v: INFO, -vv: DEBUG)'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Enable debug mode (DEBUG level, logs to ./launchsampler-debug.log)'
)
@click.option(
    '--log-file',
    type=click.Path(path_type=Path),
    default=None,
    help='Custom log file path'
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    default='INFO',
    help='Log level for file logging (default: INFO)'
)
def cli(
    ctx,
    set: Optional[str],
    mode: str,
    led_ui: bool,
    samples_dir: Optional[Path],
    verbose: int,
    debug: bool,
    log_file: Optional[Path],
    log_level: str
):
    """
    Launchpad Sampler - MIDI-controlled audio sample player for Novation Launchpad.


    The TUI provides two modes:

    \b
    - Play Mode (default): Full MIDI integration for live performance
    - Edit Mode: Build sets, assign samples, change configurations

    You can switch modes anytime by pressing E (edit) or P (play).
    A full list of shortcuts is available in the palette (press ctrl+p)

    You can either load an existing set by name, or load samples from a directory.

    \b
    Examples:
      # Create new empty set
      launchsampler

    # Start in play mode with saved set
      launchsampler --set my-drums

      # Start in edit mode to configure a set
      launchsampler --set my-drums --mode edit

      # Load from samples directory
      launchsampler --samples-dir ./samples



      # Enable debug logging
      launchsampler --debug

      # Custom log file
      launchsampler --log-file ./my-session.log

      # List audio devices
      launchsampler audio list

      # List MIDI devices
      launchsampler midi list
    """
    # If a subcommand was invoked, don't run the app
    if ctx.invoked_subcommand is not None:
        return

    # Lazy imports to avoid loading heavy dependencies during doc generation
    from launchsampler.models import AppConfig
    from launchsampler.orchestration import Orchestrator
    from launchsampler.tui import LaunchpadSampler
    from launchsampler.led_ui import LaunchpadLEDUI

    # Setup logging (TUI uses stdout, so we log to files)
    setup_logging(verbose, debug, log_file, log_level)

    logger.info("Starting Launchpad Sampler Application")

    # Determine log file path for error message
    if debug and not log_file:
        log_path = Path.cwd() / "launchsampler-debug.log"
    elif log_file:
        log_path = log_file
    else:
        config_dir = Path.home() / ".launchsampler" / "logs"
        log_path = config_dir / "launchsampler.log"

    # Setup and run application with error handling
    try:
        # Load configuration
        config_obj = AppConfig.load_or_default()

        # Save config
        config_obj.save()

        # Create orchestrator (NOT initialized yet)
        orchestrator = Orchestrator(
            config=config_obj,
            set_name=set,
            samples_dir=samples_dir,
            start_mode=mode.lower(),
            headless=False
        )

        # Create TUI (NOT initialized yet)
        tui = LaunchpadSampler(
            orchestrator=orchestrator,
            start_mode=mode.lower()
        )

        # Register TUI with orchestrator
        orchestrator.register_ui(tui)

        # Create and register LED UI if enabled
        if led_ui:
            logger.info("LED UI enabled - creating LaunchpadLEDUI")
            led = LaunchpadLEDUI(orchestrator=orchestrator, poll_interval=5.0)
            orchestrator.register_ui(led)
        else:
            logger.info("LED UI disabled")

        # Run orchestrator (will initialize and start UIs)
        # The TUI will initialize the orchestrator once it's running
        orchestrator.run()

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        logger.info("Application interrupted by user")
        click.echo("\nShutting down...", err=True)
    except SystemExit as e:
        # Handle clean exit from TUI (e.g., when audio device fails)
        # SystemExit is a clean exit - don't show traceback, just exit with the code
        if e.code != 0:
            logger.error(f"Application exited with error code: {e.code}")
        import sys
        sys.exit(e.code)
    except click.Abort:
        # Re-raise Click's Abort exception without modification
        raise
    except Exception as e:
        from launchsampler.exceptions import format_error_for_display

        logger.exception("Error running application")

        # Format error message (handles both custom and standard exceptions)
        user_message, recovery_hint = format_error_for_display(e)

        # Show clean error message without traceback
        click.echo("\n" + "="*70, err=True)
        click.echo(f"ERROR: {user_message}", err=True)
        click.echo("="*70, err=True)

        # Show recovery hint if available
        if recovery_hint:
            click.echo(f"\n{recovery_hint}", err=True)

        click.echo(f"\nFor details, check the log file: {log_path}", err=True)
        click.echo("For logging options, run: launchsampler --help", err=True)

        # Exit with error code without showing traceback
        import sys
        sys.exit(1)
    finally:
        # Ensure proper cleanup if orchestrator was created
        if 'orchestrator' in locals():
            orchestrator.shutdown()


# Register utility commands
cli.add_command(audio_group)
cli.add_command(midi_group)
cli.add_command(config)
cli.add_command(test)

if __name__ == "__main__":
    cli()
