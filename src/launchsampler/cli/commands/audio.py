"""Audio command implementations."""

import click

from launchsampler.audio import AudioDevice


@click.group(name="audio")
def audio_group():
    """Audio device commands."""
    pass


def _display_device_details(info: dict, indent: str = "    ") -> None:
    """Display device details with specified indentation."""
    click.echo(f"{indent}Channels: {info['max_output_channels']} out")
    click.echo(f"{indent}Sample Rate: {info['default_samplerate']} Hz")
    if 'default_low_output_latency' in info:
        latency_ms = info['default_low_output_latency'] * 1000
        click.echo(f"{indent}Latency: {latency_ms:.1f} ms")
    click.echo("")


@audio_group.command(name="list")
@click.option("--all", is_flag=True, help="Show all audio devices, not just low-latency ones")
@click.option("--detailed", is_flag=True, help="Show detailed device information")
def list_audio(all: bool, detailed: bool):
    """List available audio output devices."""
    devices, api_names = AudioDevice.list_output_devices(all_devices=all)
    default_device_id = AudioDevice.get_default_device()

    if all:
        devices_by_api = AudioDevice.get_devices_by_host_api(all_devices=True)

        # Display available APIs
        hostapis = AudioDevice.get_all_host_apis()
        click.echo("Available Audio APIs:")
        for api in hostapis:
            is_default = any(d[2] == api['name'] for d in devices if d[0] == default_device_id)
            if is_default:
                click.echo(f"  - {api['name']} (default)")
            else:
                click.echo(f"  - {api['name']}")
        click.echo()

        # Display devices grouped by API
        for host_api_name, api_devices in devices_by_api.items():
            click.echo(f"{host_api_name} Devices:")
            for device_id, name, info in api_devices:
                is_default = device_id == default_device_id
                if is_default:
                    click.echo(f"  [{device_id}] {name}  [Default]")
                else:
                    click.echo(f"  [{device_id}] {name}")

                if detailed:
                    _display_device_details(info, indent="      ")
            click.echo()
    else:
        # Low-latency only mode
        click.echo(f"Available low-latency audio output devices ({api_names}):\n")

        if not devices:
            click.echo(f"No {api_names} devices found.")
            click.echo(f"\nNote: Only {api_names} devices are supported for low-latency playback.")
            return

        for device_id, name, host_api, info in devices:
            is_default = device_id == default_device_id
            if is_default:
                click.echo(f"[{device_id}] {name}  [Default]")
            else:
                click.echo(f"[{device_id}] {name}")
            click.echo(f"    Host API: {host_api}")
            _display_device_details(info)
            click.echo()  # Blank line between devices
