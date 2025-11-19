# Configuration

LaunchSampler uses a JSON configuration file to store settings. The config is automatically created on first run.

## Configuration File Location

=== "Linux / macOS"
    ```
    ~/.launchsampler/config.json
    ```

=== "Windows"
    ```
    %USERPROFILE%\.launchsampler\config.json
    ```

## Default Configuration

```json
{
  "sets_dir": "~/.launchsampler/sets",
  "default_audio_device": null,
  "default_buffer_size": 512,
  "midi_poll_interval": 2.0,
  "panic_button_cc_control": 19,
  "panic_button_cc_value": 127,
  "last_set": null,
  "auto_save": true
}
```

## Configuration Options

### Path Settings

#### `sets_dir`
- **Type:** `string`
- **Default:** `"~/.launchsampler/sets"`
- **Description:** Default directory for saving/loading sets

### Audio Settings

#### `default_audio_device`
- **Type:** `integer | null`
- **Default:** `null` (use system default)
- **Description:** Default audio output device ID
- **Note:** Use `launchsampler audio list` to find device IDs
- **Fallback Behavior:**
  - If `null`: Uses the OS default audio device
  - If invalid (device unplugged, doesn't exist, or uses non-low-latency API): Automatically falls back to the OS default device with a warning
  - If OS default is also invalid: Searches for any available low-latency audio device
  - Only low-latency APIs are supported (Windows: ASIO/WASAPI, macOS: Core Audio, Linux: ALSA/JACK)

#### `default_buffer_size`
- **Type:** `integer`
- **Default:** `512`
- **Common values:** `128`, `256`, `512`, `1024`, `2048`
- **Description:** Audio buffer size in frames
- **Note:** Lower = less latency but higher CPU usage; higher = more stable but more latency

### MIDI Settings

#### `midi_poll_interval`
- **Type:** `float`
- **Default:** `2.0`
- **Description:** How often to check for MIDI device changes (in seconds)

#### `panic_button_cc_control`
- **Type:** `integer`
- **Default:** `19`
- **Description:** MIDI CC control number for panic button (stops all audio)

#### `panic_button_cc_value`
- **Type:** `integer`
- **Default:** `127`
- **Description:** MIDI CC value that triggers the panic button

### Session Settings

#### `last_set`
- **Type:** `string | null`
- **Default:** `null`
- **Description:** Name of the last loaded set (auto-updated)

#### `auto_save`
- **Type:** `boolean`
- **Default:** `true`
- **Description:** Automatically save changes to sets

## Listing Available Devices

### List Audio Devices

List low-latency audio devices only (default):

```bash
launchsampler audio list
```

Output example:
```
Available low-latency audio output devices (ASIO/WASAPI):

[2] Speakers (Realtek)  [Default]
    Host API: Windows WASAPI
    Channels: 2 out
    Sample Rate: 48000.0 Hz
    Latency: 3.0 ms

[3] Headphones (USB Audio)
    Host API: Windows WASAPI
    Channels: 2 out
    Sample Rate: 48000.0 Hz
    Latency: 3.0 ms
```

List all audio devices (including non-low-latency):

```bash
launchsampler audio list --all
```

Output example:
```
Available Audio APIs:
  - MME (default)
  - DirectSound
  - Windows WASAPI

MME Devices:
  [0] Speakers (Realtek High Definition Audio)  [Default]
  [1] Headphones (USB Audio Device)

DirectSound Devices:
  [4] Speakers (Realtek)
  [5] Headphones (USB Audio)

Windows WASAPI Devices:
  [2] Speakers (Realtek)  [Default]
  [3] Headphones (USB Audio)
```

List all audio devices with detailed information:

```bash
launchsampler audio list --all --detailed
```

Output example:
```
Available Audio APIs:
  - MME (default)
  - DirectSound
  - Windows WASAPI

MME Devices:
  [0] Speakers (Realtek High Definition Audio)  [Default]
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 10.0 ms
  [1] Headphones (USB Audio Device)
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 10.0 ms

DirectSound Devices:
  [4] Speakers (Realtek)
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 8.0 ms
  [5] Headphones (USB Audio)
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 8.0 ms

Windows WASAPI Devices:
  [2] Speakers (Realtek)  [Default]
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 3.0 ms
  [3] Headphones (USB Audio)
      Channels: 2 out
      Sample Rate: 48000.0 Hz
      Latency: 3.0 ms
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

## Editing Configuration

### Method 1: Manual Edit

Edit the JSON file directly:

```bash
# Linux / macOS
nano ~/.launchsampler/config.json

# Windows
notepad %USERPROFILE%\.launchsampler\config.json
```

### Method 2: Python API

```python
from launchsampler.models import AppConfig
from pathlib import Path

# Load config
config = AppConfig.load_or_default()

# Modify settings
config.default_audio_device = 3
config.default_buffer_size = 256
config.midi_poll_interval = 1.0
config.auto_save = True

# Save config
config.save()
```

## Logging

LaunchSampler provides flexible logging options to help you troubleshoot issues and monitor application behavior.

### Log File Locations

By default, logs are stored in your config directory:

=== "Linux / macOS"
    ```
    ~/.launchsampler/logs/launchsampler.log
    ```

=== "Windows"
    ```
    %USERPROFILE%\.launchsampler\logs\launchsampler.log
    ```

### Logging Options

#### Default Behavior (No Flags)

```bash
launchsampler
```

- **Log Level:** WARNING
- **Log File:** `~/.launchsampler/logs/launchsampler.log`
- **Behavior:** Only warnings and errors are logged

#### Verbose Mode

```bash
launchsampler -v              # INFO level
launchsampler -vv             # DEBUG level
```

- **`-v`:** Includes informational messages (INFO level)
- **`-vv`:** Includes detailed debug information (DEBUG level)
- **Log File:** Same default location

#### Debug Mode

```bash
launchsampler --debug
```

- **Log Level:** DEBUG
- **Log File:** `./launchsampler-debug.log` (current directory)
- **Use Case:** Troubleshooting - creates log file in current directory for easy access

#### Custom Log File

```bash
launchsampler --log-file ./my-session.log
```

- **Log Level:** INFO (default)
- **Log File:** Custom path you specify
- **Use Case:** Recording specific sessions

#### Custom Log Level

```bash
launchsampler --log-file ./session.log --log-level DEBUG
```

- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`
- **Use Case:** Fine-tune logging detail for custom log files

### Log Rotation

Logs are automatically rotated to prevent excessive disk usage:

- **Maximum file size:** 10 MB
- **Backup files kept:** 5
- **Files:** `launchsampler.log`, `launchsampler.log.1`, ..., `launchsampler.log.5`

### Common Logging Scenarios

#### Debugging Startup Issues

```bash
launchsampler --debug
```

Check `./launchsampler-debug.log` for detailed startup information.

#### Recording a Performance Session

```bash
launchsampler --set my-drums --log-file ./performance-2024-01-15.log
```

Logs are saved to a timestamped file in the current directory.

#### Monitoring Long-Running Sessions

```bash
launchsampler -v
```

INFO-level logs in default location help track application behavior over time.

#### Silent Operation

```bash
launchsampler
# Only warnings and errors are logged
```

Minimal logging for production use.

### Reading Log Files

Log entries follow this format:

```
2024-01-15 14:30:22 - launchsampler.player - INFO - Starting audio playback
2024-01-15 14:30:22 - launchsampler.midi - WARNING - MIDI device disconnected
2024-01-15 14:30:23 - launchsampler.audio - ERROR - Audio buffer underrun
```

Each line contains:
1. **Timestamp:** When the event occurred
2. **Logger name:** Which component generated the log
3. **Level:** Severity (DEBUG, INFO, WARNING, ERROR)
4. **Message:** Description of the event

### Viewing Logs in Real-Time

While the TUI is running, logs are only written to files. To monitor logs in real-time:

=== "Linux / macOS"
    ```bash
    # In another terminal
    tail -f ~/.launchsampler/logs/launchsampler.log
    ```

=== "Windows (PowerShell)"
    ```powershell
    # In another terminal
    Get-Content $env:USERPROFILE\.launchsampler\logs\launchsampler.log -Wait
    ```

### Troubleshooting with Logs

When reporting issues or debugging problems:

1. **Enable debug logging:**
   ```bash
   launchsampler --debug
   ```

2. **Reproduce the issue** while the app is running

3. **Check the log file:**
   ```bash
   cat launchsampler-debug.log
   ```

4. **Look for ERROR or WARNING messages** near the time of the issue

5. **Share relevant log sections** when asking for help

!!! tip "Performance Impact"
    DEBUG logging has minimal performance impact for most use cases. Only in very high-throughput scenarios (many simultaneous samples) should you consider using WARNING level.

### Logging Troubleshooting

#### No Log File Created

**Problem:** Log file doesn't exist after running the application.

**Solutions:**

1. **Check the correct location:**
   ```bash
   # Linux/macOS
   ls -la ~/.launchsampler/logs/

   # Windows
   dir %USERPROFILE%\.launchsampler\logs\
   ```

2. **Check permissions:**
   ```bash
   # Linux/macOS - ensure write permissions
   chmod 755 ~/.launchsampler/logs/
   ```

3. **Run with debug mode to create log in current directory:**
   ```bash
   launchsampler --debug
   ls -la launchsampler-debug.log
   ```

#### Log File is Empty

**Problem:** Log file exists but contains no entries.

**Possible Causes:**

- Application crashed before logging initialized
- Insufficient permissions
- Disk space full

**Solutions:**

1. **Check disk space:**
   ```bash
   df -h  # Linux/macOS
   ```

2. **Try a different location:**
   ```bash
   launchsampler --log-file ~/Desktop/test.log
   ```

3. **Check for application errors on stderr:**
   ```bash
   launchsampler 2> errors.txt
   # Check errors.txt for startup issues
   ```

#### Can't Find Recent Logs

**Problem:** Looking for logs but finding old entries.

**Solutions:**

1. **Check log rotation - newer logs may be in backup files:**
   ```bash
   # View most recent log first
   ls -lt ~/.launchsampler/logs/

   # Check all log files
   tail ~/.launchsampler/logs/launchsampler.log*
   ```

2. **Use debug mode for fresh log in current directory:**
   ```bash
   launchsampler --debug
   ```

#### Too Much Log Output

**Problem:** Log files growing too large or too many debug messages.

**Solutions:**

1. **Reduce log level:**
   ```bash
   # Use default (WARNING only)
   launchsampler

   # Or specify WARNING explicitly
   launchsampler --log-file ./session.log --log-level WARNING
   ```

2. **Adjust rotation settings** by modifying the code (advanced):
   - Change `maxBytes` in `setup_logging()` function
   - Change `backupCount` to keep fewer files

#### Logs Not Showing Expected Information

**Problem:** Missing log entries for specific operations.

**Solutions:**

1. **Increase verbosity:**
   ```bash
   launchsampler -vv  # DEBUG level shows everything
   ```

2. **Check you're looking at the right log file:**
   ```bash
   # Debug mode creates logs in current directory
   launchsampler --debug
   cat ./launchsampler-debug.log

   # Default mode uses config directory
   cat ~/.launchsampler/logs/launchsampler.log
   ```

3. **Ensure the operation actually executed** - some operations may fail silently

#### Permission Denied Errors

**Problem:** Can't write to log file location.

=== "Linux / macOS"
    ```bash
    # Fix permissions on config directory
    mkdir -p ~/.launchsampler/logs
    chmod 755 ~/.launchsampler/logs
    ```

=== "Windows"
    ```powershell
    # Run as administrator or use a different location
    launchsampler --log-file %USERPROFILE%\Desktop\launchsampler.log
    ```

#### Log File Location on Windows

**Problem:** Can't find `%APPDATA%` on Windows.

**Solutions:**

1. **Open file explorer and type in address bar:**
   ```
   %USERPROFILE%\.launchsampler\logs
   ```

2. **Or use full path:**
   ```
   C:\Users\YourUsername\.launchsampler\logs
   ```

3. **Or use PowerShell:**
   ```powershell
   cd $env:USERPROFILE\.launchsampler\logs
   dir
   ```

## Troubleshooting

### Audio Dropouts / Glitches

**Increase buffer size:**
```json
{
  "default_buffer_size": 1024
}
```

### High Latency

**Decrease buffer size** (if your system can handle it):
```json
{
  "default_buffer_size": 256
}
```

### Wrong Audio Device

**List devices and set explicitly:**
```bash
launchsampler audio list
```

Then set the device ID in config:
```json
{
  "default_audio_device": 3
}
```
midi list
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
