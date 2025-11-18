# Installation

LaunchSampler can be installed using pip or uv. We recommend using `uv` for faster dependency resolution and installation.

## Requirements

- **Python 3.12 or higher**
- **Audio output device** (soundcard)
- Optional: **Novation Launchpad** (Mini MK3, Pro MK3, X, or compatible device)

### Supported Platforms

- ✅ Windows
- ✅ macOS
- ✅ Linux

## Installation Methods

=== "Using pipx (Recommended for CLI usage)"

    Install once, use anywhere. After installation, simply run `launchsampler` from any directory.

    ```bash
    # Install pipx (if not already installed)
    pip install pipx
    pipx ensurepath

    # Install launchsampler
    pipx install git+https://github.com/jacobanana/launchsampler
    ```

    Now you can run:
    ```bash
    launchsampler --help
    ```

=== "Using uvx (Faster, but requires full command)"

    [uv](https://github.com/astral-sh/uv) is significantly faster but requires the full git URL each time.

    ```bash
    # Install uv (if not already installed)
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Run directly (no installation needed)
    uvx git+https://github.com/jacobanana/launchsampler
    ```

## Verify Installation

After installation, verify that LaunchSampler is installed correctly:

=== "pipx"

    ```bash
    # Check version
    launchsampler --version

    # Show help
    launchsampler --help
    ```

=== "uvx"

    ```bash
    # Check version
    uvx git+https://github.com/jacobanana/launchsampler --version

    # Show help
    uvx git+https://github.com/jacobanana/launchsampler --help
    ```

## Development Installation

For development, install uv and clone the repository and install with development dependencies:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/jacobanana/launchsampler.git
cd launchsampler

# Install with development dependencies using uv
uv sync

# Run tests to verify
uv run pytest

# Run app
uv run launchsampler
```

## Troubleshooting

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
