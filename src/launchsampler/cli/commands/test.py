"""Test command for Launchpad lighting modes."""

import time
import logging

import click
import mido

from launchsampler.midi import MidiManager
from launchsampler.devices.launchpad import LaunchpadDevice

logger = logging.getLogger(__name__)


# SysEx headers - mido automatically adds F0 and F7, so we only include the data bytes
# Launchpad X: 00h 20h 29h 02h 0Ch
# Launchpad Mini MK3: 00h 20h 29h 02h 0Dh
# Launchpad Pro MK3: 00h 20h 29h 02h 0Eh
SYSEX_HEADER_LPX = [0x00, 0x20, 0x29, 0x02, 0x0C]
SYSEX_HEADER_MINI = [0x00, 0x20, 0x29, 0x02, 0x0D]
SYSEX_HEADER_PRO = [0x00, 0x20, 0x29, 0x02, 0x0E]


def detect_launchpad_type(port_name):
    """Detect Launchpad type based on port name."""
    if "Mini" in port_name or "LPMiniMK3" in port_name:
        return "mini"
    elif "Pro" in port_name or "LPProMK3" in port_name:
        return "pro"
    return "x"  # Default to X


def enter_programmer_mode(midi_manager, port_name):
    """Enter Programmer mode using SysEx message.

    Launchpad X: 00h 20h 29h 02h 0Ch 0Eh 01h
    Launchpad Mini: 00h 20h 29h 02h 0Dh 0Eh 01h
    Launchpad Pro: 00h 20h 29h 02h 0Eh 0Eh 01h
    (Programmer/Live mode switch, mode=1 for Programmer)
    """
    lp_type = detect_launchpad_type(port_name)
    if lp_type == "mini":
        header = SYSEX_HEADER_MINI
    elif lp_type == "pro":
        header = SYSEX_HEADER_PRO
    else:
        header = SYSEX_HEADER_LPX

    sysex_data = header + [0x0E, 0x01]
    msg = mido.Message('sysex', data=sysex_data)

    if midi_manager.send(msg):
        click.echo(f"[OK] Entered Programmer mode (Launchpad {lp_type.upper()})")
        return True
    else:
        click.echo("[FAIL] Failed to enter Programmer mode")
        return False


def exit_programmer_mode(midi_manager, port_name):
    """Exit Programmer mode (return to Live mode).

    Launchpad X: 00h 20h 29h 02h 0Ch 0Eh 00h
    Launchpad Mini: 00h 20h 29h 02h 0Dh 0Eh 00h
    Launchpad Pro: 00h 20h 29h 02h 0Eh 0Eh 00h
    (Programmer/Live mode switch, mode=0 for Live)
    """
    lp_type = detect_launchpad_type(port_name)
    if lp_type == "mini":
        header = SYSEX_HEADER_MINI
    elif lp_type == "pro":
        header = SYSEX_HEADER_PRO
    else:
        header = SYSEX_HEADER_LPX

    sysex_data = header + [0x0E, 0x00]
    msg = mido.Message('sysex', data=sysex_data)

    if midi_manager.send(msg):
        click.echo("[OK] Exited Programmer mode")
        return True
    else:
        click.echo("[FAIL] Failed to exit Programmer mode")
        return False


def send_led_sysex(midi_manager, port_name, led_specs):
    """Send LED lighting via SysEx message (much more efficient).

    LED lighting SysEx message format:
    Header + 03h + <colourspec> [<colourspec> [...]]

    <colourspec> structure:
    - Lighting type (1 byte): 0=static, 1=flashing, 2=pulsing, 3=RGB
    - LED index (1 byte): 0-127
    - Lighting data (1-3 bytes):
        - Type 0 (static): 1 byte palette entry
        - Type 1 (flashing): 2 bytes (color B, color A)
        - Type 2 (pulsing): 1 byte palette entry
        - Type 3 (RGB): 3 bytes (R, G, B, each 0-127)

    Args:
        midi_manager: MIDI output manager
        port_name: Port name for device detection
        led_specs: List of tuples (lighting_type, led_index, *data)

    Returns:
        True if sent successfully
    """
    lp_type = detect_launchpad_type(port_name)
    if lp_type == "mini":
        header = SYSEX_HEADER_MINI
    elif lp_type == "pro":
        header = SYSEX_HEADER_PRO
    else:
        header = SYSEX_HEADER_LPX

    # Build SysEx data: header + command (03h) + color specs
    sysex_data = header + [0x03]

    for spec in led_specs:
        lighting_type = spec[0]
        led_index = spec[1]
        data_bytes = spec[2:]

        sysex_data.append(lighting_type)
        sysex_data.append(led_index)
        sysex_data.extend(data_bytes)

    msg = mido.Message('sysex', data=sysex_data)
    success = midi_manager.send(msg)

    if not success:
        logger.warning(f"Failed to send LED SysEx message with {len(led_specs)} specs")

    return success


def set_pad_static(midi_manager, port_name, note, color):
    """Set pad to static color using SysEx.

    Args:
        midi_manager: MIDI output manager
        port_name: Port name for device detection
        note: Pad note number (0-127)
        color: Palette color index (0-127)
    """
    return send_led_sysex(midi_manager, port_name, [(0, note, color)])


def set_pad_flashing(midi_manager, port_name, note, color):
    """Set pad to flashing color using SysEx.

    Args:
        midi_manager: MIDI output manager
        port_name: Port name for device detection
        note: Pad note number (0-127)
        color: Palette color index (0-127)
    """
    # Flashing: color B (off), color A (on)
    return send_led_sysex(midi_manager, port_name, [(1, note, 0, color)])


def set_pad_pulsing(midi_manager, port_name, note, color):
    """Set pad to pulsing color using SysEx.

    Args:
        midi_manager: MIDI output manager
        port_name: Port name for device detection
        note: Pad note number (0-127)
        color: Palette color index (0-127)
    """
    return send_led_sysex(midi_manager, port_name, [(2, note, color)])


def clear_all_pads(midi_manager, port_name):
    """Clear all pads efficiently with a single SysEx message.

    Args:
        midi_manager: MIDI output manager
        port_name: Port name for device detection
    """
    # Clear all 128 possible LEDs in one message
    led_specs = [(0, i, 0) for i in range(128)]
    return send_led_sysex(midi_manager, port_name, led_specs)


@click.command(name="test")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def test(verbose):
    """
    Test Launchpad lighting modes.

    Connects to a Launchpad, enters Programmer mode, and demonstrates
    static, flashing, and pulsing LED modes on various pads.

    Press Ctrl+C to stop and exit.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    click.echo("Launchpad Lighting Test\n")

    # Create MIDI manager for Launchpad
    midi_manager = MidiManager(
        device_filter=LaunchpadDevice.matches,
        poll_interval=5.0,
        port_selector=LaunchpadDevice.select_port
    )

    try:
        # Start the MIDI manager
        click.echo("Starting MIDI manager...")
        midi_manager.start()

        # Wait for connection
        click.echo("Waiting for Launchpad connection...")
        timeout = 10
        start_time = time.time()

        while not midi_manager.is_connected:
            if time.time() - start_time > timeout:
                click.echo("\n[FAIL] No Launchpad found within timeout period")
                click.echo("\nAvailable MIDI ports:")
                ports = MidiManager.list_ports()
                for port in ports['output']:
                    click.echo(f"  - {port}")
                return
            time.sleep(0.1)

        port_name = midi_manager.current_output_port
        click.echo(f"[OK] Connected to: {port_name}\n")

        # Enter Programmer mode
        if not enter_programmer_mode(midi_manager, port_name):
            return

        time.sleep(0.2)  # Give device time to switch modes

        click.echo("\nDiagnostic: Lighting all pads red using SysEx...")
        # Light ALL pads (0-127) in red using a single SysEx message
        led_specs = [(0, i, 0x05) for i in range(128)]  # Type 0 = static, color 0x05 = red
        if send_led_sysex(midi_manager, port_name, led_specs):
            click.echo("  [OK] SysEx message sent successfully")
        else:
            click.echo("  [FAIL] Failed to send SysEx - device may not be connected")
            return

        time.sleep(2)  # Let user see the diagnostic

        click.echo("\nClearing diagnostic...")
        if not clear_all_pads(midi_manager, port_name):
            click.echo("  [FAIL] Failed to clear pads")

        time.sleep(0.5)

        click.echo("\nSetting up lighting pattern...")

        # Pad layout (Programmer mode):
        # Bottom left = 11, Bottom right = 18
        # Top left = 81, Top right = 88

        # Build all LED specs in one batch for efficiency
        click.echo("  Static colors (bottom row):")
        click.echo("  Flashing colors (second row):")
        click.echo("  Pulsing colors (third row):")

        led_specs = []

        # Static colors - bottom row (Type 0)
        led_specs.extend([
            (0, 11, 0x05),  # Red
            (0, 12, 0x0D),  # Yellow
            (0, 13, 0x15),  # Green
            (0, 14, 0x2D),  # Blue
        ])

        # Flashing colors - second row (Type 1: color_b, color_a)
        led_specs.extend([
            (1, 21, 0, 0x15),  # Green flash
            (1, 22, 0, 0x35),  # Pink flash
            (1, 23, 0, 0x25),  # Turquoise flash
        ])

        # Pulsing colors - third row (Type 2)
        led_specs.extend([
            (2, 31, 0x2D),  # Blue pulse
            (2, 32, 0x35),  # Pink pulse
            (2, 33, 0x0D),  # Yellow pulse
        ])

        # Send all LEDs in a single SysEx message!
        if send_led_sysex(midi_manager, port_name, led_specs):
            click.echo("    [OK] All LEDs set via single SysEx message")
        else:
            click.echo("    [FAIL] Failed to set LEDs")

        click.echo("\n[OK] Lighting test complete!")
        click.echo("\nThe Launchpad should now display:")
        click.echo("  - Bottom row: Static red, yellow, green, blue")
        click.echo("  - Second row: Flashing green, pink, turquoise")
        click.echo("  - Third row: Pulsing blue, pink, yellow")
        click.echo("\nPress Ctrl+C to clear and exit...")

        # Wait for user interrupt
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        click.echo("\n\nCleaning up...")

        # Clear all pads
        click.echo("Clearing all pads...")
        clear_all_pads(midi_manager, port_name)

        time.sleep(0.2)

        # Exit Programmer mode
        exit_programmer_mode(midi_manager, port_name)

    finally:
        click.echo("Stopping MIDI manager...")
        midi_manager.stop()
        click.echo("✓ Done")
