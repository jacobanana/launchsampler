"""Main CLI entry point."""

import logging
from pathlib import Path
from typing import Optional

import click

from .commands import audio_group, midi_group, config, test
from launchsampler.models import AppConfig
from launchsampler.app import LaunchpadSamplerApp
from launchsampler.tui import LaunchpadSampler
from launchsampler.led_ui import LaunchpadLEDUI


logger = logging.getLogger(__name__)


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
def cli(ctx, set: Optional[str], mode: str, led_ui: bool, samples_dir: Optional[Path]):
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
      # Start in play mode with saved set (default)
      launchsampler --set my-drums

      # Start in edit mode to configure
      launchsampler --set my-drums --mode edit

      # Load from samples directory
      launchsampler --samples-dir ./samples

      # Create new empty set
      launchsampler

      # List audio devices
      launchsampler audio list

      # List MIDI devices
      launchsampler midi list
    """
    # If a subcommand was invoked, don't run the app
    if ctx.invoked_subcommand is not None:
        return

    # Setup logging to file (TUI uses stdout)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='launchsampler.log'
    )

    logger.info("Starting Launchpad Sampler Application")

    # Load configuration
    config_obj = AppConfig.load_or_default()

    # Save config
    config_obj.save()

    # Create orchestrator (NOT initialized yet)
    orchestrator = LaunchpadSamplerApp(
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
    try:
        orchestrator.run()
    except Exception as e:
        logger.exception("Error running application")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    finally:
        # Ensure proper cleanup
        orchestrator.shutdown()


# Register utility commands
cli.add_command(audio_group)
cli.add_command(midi_group)
cli.add_command(config)
cli.add_command(test)

if __name__ == "__main__":
    cli()
