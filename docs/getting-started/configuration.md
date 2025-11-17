# Configuration

LaunchSampler uses a JSON configuration file to store settings. The config is automatically created on first run.

## Configuration File Location

=== "Linux / macOS"
    ```
    ~/.config/launchsampler/config.json
    ```

=== "Windows"
    ```
    %APPDATA%\launchsampler\config.json
    ```

## Default Configuration

```json
{
  "audio_device_api": null,
  "audio_device_id": null,
  "sample_rate": 44100,
  "buffer_size": 512,
  "default_mode": "play",
  "sets_dir": "~/.config/launchsampler/sets"
}
```

## Configuration Options

### Audio Settings

#### `audio_device_api`
- **Type:** `string | null`
- **Default:** `null` (auto-detect)
- **Description:** Audio API to use (e.g., "MME", "DirectSound", "WASAPI", "ASIO" on Windows)

#### `audio_device_id`
- **Type:** `integer | null`
- **Default:** `null` (use default device)
- **Description:** Specific audio device ID to use

#### `sample_rate`
- **Type:** `integer`
- **Default:** `44100`
- **Options:** `44100`, `48000`, `96000`
- **Description:** Audio sample rate in Hz

#### `buffer_size`
- **Type:** `integer`
- **Default:** `512`
- **Options:** `128`, `256`, `512`, `1024`, `2048`
- **Description:** Audio buffer size in frames
- **Note:** Lower = less latency, higher CPU usage

### Application Settings

#### `default_mode`
- **Type:** `string`
- **Default:** `"play"`
- **Options:** `"edit"`, `"play"`
- **Description:** Mode to start in

#### `sets_dir`
- **Type:** `string`
- **Default:** `"~/.config/launchsampler/sets"`
- **Description:** Default directory for saving/loading sets

## Listing Available Devices

### List Audio Devices

```bash
launchsampler --list-audio
```

Output example:
```
Available Audio APIs:
  - MME (default)
  - DirectSound
  - WASAPI

MME Devices:
  [0] Speakers (Realtek High Definition Audio)  [Default]
  [1] Headphones (USB Audio Device)

WASAPI Devices:
  [2] Speakers (Realtek) [Default]
  [3] Headphones (USB Audio)
```

### List MIDI Devices

```bash
launchsampler --list-midi
```

Output example:
```
Available MIDI Input Devices:
  [0] Launchpad Mini MK3 MIDI In
  [1] MIDI Keyboard In

Available MIDI Output Devices:
  [0] Launchpad Mini MK3 MIDI Out
  [1] MIDI Keyboard Out
```

## Example Configurations

### Low Latency (ASIO)

For professional audio interfaces with ASIO support:

```json
{
  "audio_device_api": "ASIO",
  "audio_device_id": 0,
  "sample_rate": 48000,
  "buffer_size": 128,
  "default_mode": "play",
  "sets_dir": "~/Music/LaunchSampler/Sets"
}
```

!!! warning "Low Latency"
    Buffer size of 128 provides ~3ms latency but requires fast CPU and quality audio interface

### High Compatibility (Default Device)

For maximum compatibility:

```json
{
  "audio_device_api": null,
  "audio_device_id": null,
  "sample_rate": 44100,
  "buffer_size": 512,
  "default_mode": "play",
  "sets_dir": "~/.config/launchsampler/sets"
}
```

### Production Setup (USB Audio Interface)

For USB audio interfaces:

```json
{
  "audio_device_api": "WASAPI",
  "audio_device_id": 3,
  "sample_rate": 48000,
  "buffer_size": 256,
  "default_mode": "play",
  "sets_dir": "~/Documents/LaunchSampler"
}
```

## Editing Configuration

### Method 1: Manual Edit

Edit the JSON file directly:

```bash
# Linux / macOS
nano ~/.config/launchsampler/config.json

# Windows
notepad %APPDATA%\launchsampler\config.json
```

### Method 2: Python API

```python
from launchsampler.models import AppConfig
from pathlib import Path

# Load config
config = AppConfig.load_or_default()

# Modify settings
config.audio_device_api = "WASAPI"
config.buffer_size = 256
config.sample_rate = 48000

# Save config
config.save()
```

## Troubleshooting

### Audio Dropouts / Glitches

**Increase buffer size:**
```json
{
  "buffer_size": 1024
}
```

### High Latency

**Decrease buffer size** (if your system can handle it):
```json
{
  "buffer_size": 256
}
```

Or use a better audio API (ASIO on Windows, CoreAudio on macOS).

### Wrong Audio Device

**List devices and set explicitly:**
```bash
launchsampler --list-audio
```

Then set the device ID in config:
```json
{
  "audio_device_id": 3
}
```

### MIDI Not Working

**Check MIDI devices:**
```bash
launchsampler --list-midi
```

If your Launchpad is not listed:
1. Check USB connection
2. Install manufacturer drivers
3. Try a different USB port

## Next Steps

- [Quick Start](quick-start.md) - Start using LaunchSampler
- [User Guide](../user-guide/overview.md) - Learn all features
- [MIDI Integration](../user-guide/midi-integration.md) - MIDI setup details
