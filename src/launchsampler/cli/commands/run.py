"""Run command - launches unified TUI application."""

import logging
from pathlib import Path
from typing import Optional

import click

from launchsampler.models import AppConfig
from launchsampler.app import LaunchpadSamplerApp
from launchsampler.tui import LaunchpadSampler
from launchsampler.led_ui import LaunchpadLEDUI


logger = logging.getLogger(__name__)


@click.command()
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
@click.argument(
    'samples_dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False
)
def run(set: Optional[str], mode: str, led_ui: bool, samples_dir: Optional[Path]):
    """
    Launch Launchpad Sampler TUI (Text User Interface).

    The TUI provides two modes:

    \b
    - Play Mode (default): Full MIDI integration for live performance
    - Edit Mode: Build sets, assign samples, change configurations

    You can switch modes anytime by pressing E (edit) or P (play).

    You can either load an existing set by name, or load samples from a directory.

    \b
    Examples:
      # Start in play mode with saved set (default)
      launchsampler run --set my-drums

      # Start in edit mode to configure
      launchsampler run --set my-drums --mode edit

      # Load from samples directory
      launchsampler run ./samples

      # Create new empty set
      launchsampler run
    """
    # Setup logging to file (TUI uses stdout)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='launchsampler.log'
    )

    logger.info("Starting Launchpad Sampler Application")

    # Load configuration
    config = AppConfig.load_or_default()

    # Save config
    config.save()

    # Create orchestrator (NOT initialized yet)
    orchestrator = LaunchpadSamplerApp(
        config=config,
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
    try:
        orchestrator.run()
    except Exception as e:
        logger.exception("Error running application")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    finally:
        # Ensure proper cleanup
        orchestrator.shutdown()
