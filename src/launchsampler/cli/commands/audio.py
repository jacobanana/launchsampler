"""Audio command implementations."""

import click

from launchsampler.audio import AudioManager


@click.group(name="audio")
def audio_group():
    """Audio device commands."""
    pass


@audio_group.command(name="list")
def list_audio():
    """List available low-latency audio output devices."""
    devices, api_names = AudioManager.list_output_devices()

    click.echo(f"Available low-latency audio output devices ({api_names}):\n")

    if not devices:
        click.echo(f"No {api_names} devices found.")
        click.echo(f"\nNote: Only {api_names} devices are supported for low-latency playback.")
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
