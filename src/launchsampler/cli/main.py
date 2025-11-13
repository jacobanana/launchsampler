"""Main CLI entry point."""

import click

from .commands import audio_group, midi_group, run, config


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
cli.add_command(audio_group)
cli.add_command(midi_group)
cli.add_command(run)
cli.add_command(config)

if __name__ == "__main__":
    cli()
