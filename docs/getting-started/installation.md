# Installation

LaunchSampler can be installed using pip or uv. We recommend using `uv` for faster dependency resolution and installation.

## Requirements

- **Python 3.12 or higher**
- **Novation Launchpad** (Mini MK3, Pro MK3, X, or compatible device)
- **Audio output device** (soundcard)

### Supported Platforms

- ✅ Windows
- ✅ macOS
- ✅ Linux

## Installation Methods

=== "Using uv (Recommended)"

    [uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

    ```bash
    # Install uv (if not already installed)
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install LaunchSampler
    uv pip install launchsampler

    # Or install from source
    git clone https://github.com/jacobanana/launchsampler.git
    cd launchsampler
    uv sync
    ```

=== "Using pip"

    ```bash
    # Install from PyPI (when published)
    pip install launchsampler

    # Or install from source
    git clone https://github.com/jacobanana/launchsampler.git
    cd launchsampler
    pip install -e .
    ```

## Verify Installation

After installation, verify that LaunchSampler is installed correctly:

```bash
# Check version
launchsampler --version

# Show help
launchsampler --help
```

## Development Installation

For development, clone the repository and install with development dependencies:

```bash
# Clone the repository
git clone https://github.com/jacobanana/launchsampler.git
cd launchsampler

# Install with development dependencies using uv
uv sync --all-extras

# Or using pip
pip install -e ".[dev]"

# Run tests to verify
uv run pytest
```

## Troubleshooting

### MIDI Device Not Found

If LaunchSampler cannot detect your Launchpad:

1. **Check USB connection** - Ensure the Launchpad is connected
2. **Install drivers** - Some systems may need MIDI drivers
3. **List devices** - Run `launchsampler --list-midi` to see available devices

### Audio Issues

If you experience audio problems:

1. **Check audio device** - Run `launchsampler --list-audio` to see available devices
2. **Configure audio** - Edit `~/.config/launchsampler/config.json` to select device
3. **Test playback** - Try playing a sample in edit mode (Space key)

### Permission Errors (Linux)

On Linux, you may need to add your user to the `audio` group:

```bash
sudo usermod -a -G audio $USER
```

Then log out and log back in for changes to take effect.

## Next Steps

- [Quick Start Guide](quick-start.md) - Learn the basics
- [Configuration](configuration.md) - Customize your setup
- [User Guide](../user-guide/overview.md) - Master all features
