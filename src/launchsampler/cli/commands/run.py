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
    default='edit',
    help='Start in edit or play mode (default: edit)'
)
@click.option(
    '--samples-dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help='Directory containing samples (ignored if --set is used)'
)
def run(set: Optional[str], mode: str, samples_dir: Optional[Path]):
    """
    Launch Launchpad Sampler TUI (Text User Interface).

    The TUI provides two modes:

    \b
    - Edit Mode (default): Build sets, assign samples, test with preview audio
    - Play Mode: Full MIDI integration for live performance

    You can switch modes anytime by pressing E (edit) or P (play).

    \b
    Examples:
      # Start in edit mode (default)
      launchsampler run --set my-drums

      # Start in play mode with MIDI active
      launchsampler run --set my-drums --mode play

      # Load from samples directory
      launchsampler run --samples-dir ./samples

      # Create new set
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

    # Update config with CLI arguments
    if samples_dir is not None:
        config.samples_dir = samples_dir

    # Save config
    config.save()

    # Launch TUI
    from launchsampler.tui import LaunchpadSampler

    app = LaunchpadSampler(
        config=config,
        set_name=set,
        start_mode=mode.lower()
    )

    try:
        app.run()
    except Exception as e:
        logger.exception("Error running TUI")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
