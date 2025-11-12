"""List command implementations."""

import click

from ...audio import AudioManager
from ...midi import LaunchpadController


@click.group(name="list")
def list_group():
    """List available devices and ports."""
    pass


@list_group.command(name="audio")
def list_audio():
    """List available ASIO and WASAPI audio output devices."""
    click.echo("Available low-latency audio output devices (ASIO/WASAPI only):\n")

    devices = AudioManager.list_output_devices()

    if not devices:
        click.echo("No ASIO or WASAPI devices found.")
        click.echo("\nNote: Only ASIO and WASAPI devices are supported for low-latency playback.")
        return

    for device_id, name, host_api, info in devices:
        click.echo(f"[{device_id}] {name}")
        click.echo(f"    Host API: {host_api}")
        click.echo(f"    Channels: {info['max_output_channels']} out")
        click.echo(f"    Sample Rate: {info['default_samplerate']} Hz")

        # Add latency info if available
        if 'default_low_output_latency' in info:
            latency_ms = info['default_low_output_latency'] * 1000
            click.echo(f"    Latency: {latency_ms:.1f} ms")

        click.echo()  # Blank line between devices


@list_group.command(name="midi")
def list_midi():
    """List available MIDI input ports."""
    click.echo("Available MIDI input ports:\n")

    ports = LaunchpadController.list_ports()

    if not ports:
        click.echo("No MIDI input ports found.")
        return

    for i, port in enumerate(ports):
        click.echo(f"[{i}] {port}")
