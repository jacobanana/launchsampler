"""Main CLI entry point."""

import click

from .commands import list_group, run


@click.group()
@click.version_option(version="0.1.0", prog_name="launchsampler")
def cli():
    """
    Launchpad Sampler - MIDI-controlled audio sampler for Novation Launchpad.

    A simple, low-latency sampler that maps WAV files to your Launchpad pads.
    Supports hot-plug MIDI detection and ASIO/WASAPI audio for minimal latency.
    """
    pass


# Register commands
cli.add_command(list_group)
cli.add_command(run)


if __name__ == "__main__":
    cli()
