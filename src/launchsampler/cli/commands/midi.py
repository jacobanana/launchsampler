"""MIDI command implementations."""

import contextlib
import logging
import time
from collections.abc import Callable
from datetime import datetime

import click
import mido

from launchsampler.midi import MidiInputManager, MidiManager

logger = logging.getLogger(__name__)


@click.group(name="midi")
def midi_group():
    """MIDI device commands."""
    pass


@midi_group.command(name="list")
def list_midi():
    """List available MIDI ports."""
    ports = MidiManager.list_ports()

    click.echo("MIDI Input Ports:\n")
    if not ports["input"]:
        click.echo("  No MIDI input ports found.")
    else:
        for i, port in enumerate(ports["input"]):
            click.echo(f"  [{i}] {port}")

    click.echo("\nMIDI Output Ports:\n")
    if not ports["output"]:
        click.echo("  No MIDI output ports found.")
    else:
        for i, port in enumerate(ports["output"]):
            click.echo(f"  [{i}] {port}")


@midi_group.command(name="monitor")
@click.option(
    "--filter-clock/--no-filter-clock",
    default=True,
    help="Filter out clock messages (default: enabled)",
)
def monitor_midi(filter_clock: bool):
    """
    Monitor all MIDI input ports and log incoming messages.

    Connects to all available MIDI input ports and displays
    messages in real-time. Useful for debugging and testing.

    Press Ctrl+C to stop monitoring.
    """
    ports = mido.get_input_names()

    if not ports:
        click.echo("No MIDI input ports found.")
        return

    click.echo(f"Monitoring {len(ports)} MIDI input port(s):")
    for port in ports:
        click.echo(f"  - {port}")

    if filter_clock:
        click.echo("\nFiltering: clock messages (use --no-filter-clock to show all)")
    else:
        click.echo("\nShowing all messages")

    click.echo("\nPress Ctrl+C to stop\n")

    # Create input managers for each port
    managers = []

    try:
        for port_name in ports:
            # Create manager that accepts any port matching this exact name
            def make_filter(name: str) -> Callable[[str], bool]:
                return lambda p: p == name

            manager = MidiInputManager(
                device_filter=make_filter(port_name),
                poll_interval=10.0,  # Don't need frequent polling for monitoring
            )

            # Register callback to display messages
            def make_callback(name):
                def callback(msg):
                    # Filter clock if requested
                    if filter_clock and msg.type == "clock":
                        return

                    # Format timestamp
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    # Display message
                    click.echo(f"[{timestamp}] {name}: {msg}")

                return callback

            manager.on_message(make_callback(port_name))
            manager.start()
            managers.append(manager)

        # Keep running until Ctrl+C
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        click.echo("\n\nStopping monitor...")

    finally:
        # Stop all managers
        for manager in managers:
            with contextlib.suppress(Exception):
                manager.stop()
