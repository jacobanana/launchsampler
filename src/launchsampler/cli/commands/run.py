"""Run command - launches unified TUI application."""

import logging
from pathlib import Path
from typing import Optional

import click

from launchsampler.models import AppConfig

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
@click.argument(
    'samples_dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False
)
def run(set: Optional[str], mode: str, samples_dir: Optional[Path]):
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

    # Load configuration
    config = AppConfig.load_or_default()

    # Save config
    config.save()

    # Launch TUI
    from launchsampler.tui import LaunchpadSampler

    app = LaunchpadSampler(
        config=config,
        set_name=set,
        samples_dir=samples_dir,
        start_mode=mode.lower()
    )

    try:
        app.run()
    except Exception as e:
        logger.exception("Error running TUI")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
