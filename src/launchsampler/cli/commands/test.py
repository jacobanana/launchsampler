"""Test command for Launchpad lighting modes."""

import time
import logging

import click

from launchsampler.devices.launchpad import LaunchpadController
from launchsampler.models import Color

logger = logging.getLogger(__name__)


@click.command(name="test")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def test(verbose):
    """
    Test Launchpad lighting modes.

    Connects to a Launchpad, enters Programmer mode, and demonstrates
    static, flashing, pulsing, and RGB LED modes on various pads.

    Press Ctrl+C to stop and exit.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    click.echo("Launchpad Lighting Test\n")

    # Create Launchpad controller
    controller = LaunchpadController(poll_interval=5.0)

    try:
        # Start the controller
        click.echo("Starting Launchpad controller...")
        controller.start()

        # Wait for connection
        click.echo("Waiting for Launchpad connection...")
        timeout = 10
        start_time = time.time()

        while not controller.is_connected:
            if time.time() - start_time > timeout:
                click.echo("\n[FAIL] No Launchpad found within timeout period")
                return
            time.sleep(0.1)

        device_name = controller.device_name
        click.echo(f"[OK] Connected to: {device_name}")
        click.echo(f"[OK] Device automatically entered Programmer mode\n")

        time.sleep(0.5)  # Give device time to initialize

        click.echo("\n=== Testing RGB Mode ===")
        click.echo("Setting pads 0-3 (bottom row) to RGB colors...")

        # RGB colors - bottom row (pads 0-3)
        controller.set_pad_color(0, Color(r=127, g=0, b=0))     # Red
        controller.set_pad_color(1, Color(r=127, g=127, b=0))   # Yellow
        controller.set_pad_color(2, Color(r=0, g=127, b=0))     # Green
        controller.set_pad_color(3, Color(r=0, g=0, b=127))     # Blue

        click.echo("  [OK] RGB mode - 4 pads set")
        time.sleep(2)

        click.echo("\n=== Testing Flashing Mode ===")
        click.echo("Setting pads 8-10 (second row) to flashing...")

        # Flashing colors - second row (pads 8-10)
        # Palette colors: 5=red, 13=yellow, 21=green, 37=blue, 45=pink, 53=cyan
        controller.set_pad_flashing(8, 21)   # Green flash
        controller.set_pad_flashing(9, 45)   # Pink flash
        controller.set_pad_flashing(10, 53)  # Cyan flash

        click.echo("  [OK] Flashing mode - 3 pads set")
        time.sleep(2)

        click.echo("\n=== Testing Pulsing Mode ===")
        click.echo("Setting pads 16-18 (third row) to pulsing...")

        # Pulsing colors - third row (pads 16-18)
        controller.set_pad_pulsing(16, 37)  # Blue pulse
        controller.set_pad_pulsing(17, 45)  # Pink pulse
        controller.set_pad_pulsing(18, 13)  # Yellow pulse

        click.echo("  [OK] Pulsing mode - 3 pads set")
        time.sleep(2)

        click.echo("\n=== Testing Static Palette Mode ===")
        click.echo("Setting pads 24-27 (fourth row) to static palette colors...")

        # Static palette colors - fourth row (pads 24-27)
        controller.set_pad_static(24, 5)   # Red
        controller.set_pad_static(25, 13)  # Yellow
        controller.set_pad_static(26, 21)  # Green
        controller.set_pad_static(27, 37)  # Blue

        click.echo("  [OK] Static palette mode - 4 pads set")

        click.echo("\n[OK] Lighting test complete!")
        click.echo("\nThe Launchpad should now display:")
        click.echo("  - Row 0 (bottom): RGB red, yellow, green, blue")
        click.echo("  - Row 1: Flashing green, pink, cyan")
        click.echo("  - Row 2: Pulsing blue, pink, yellow")
        click.echo("  - Row 3: Static palette red, yellow, green, blue")
        click.echo("\nPress Ctrl+C to clear and exit...")

        # Wait for user interrupt
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        click.echo("\n\nCleaning up...")

        # Clear all pads (done automatically in stop())

    finally:
        click.echo("Stopping controller...")
        controller.stop()
        click.echo("[OK] Controller stopped (automatically exited Programmer mode)")
        click.echo("✓ Done")
