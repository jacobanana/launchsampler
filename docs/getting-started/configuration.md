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

## Configuration Options

| Field | Type | Default | Description | Notes |
|-------|------|---------|-------------|-------|
| **Path Settings** |
| `sets_dir` | `string` | `~/.launchsampler/sets` | Default directory for saving/loading sets | Set: `--sets-dir <path>` |
| **Audio Settings** |
| `default_audio_device` | `int \| null` | `null` | Audio output device ID (null = system default) | Set: `config set -a <id>`<br>Reset: `config reset default_audio_device --yes`<br>List devices: `audio list`<br>⚠️ Auto-fallback on invalid device |
| `default_buffer_size` | `int` | `512` | Audio buffer size in frames | Set: `config set -b <size>`<br>Common: `128`, `256`, `512`, `1024`, `2048`<br>Lower = less latency, higher CPU |
| **MIDI Settings** |
| `midi_poll_interval` | `float` | `2.0` | MIDI device polling interval (seconds) | Set: `--midi-poll-interval <float>` |
| `panic_button_cc_control` | `int` | `19` | MIDI CC control for panic button | Set: `--panic-button-cc-control <int>` |
| `panic_button_cc_value` | `int` | `127` | MIDI CC value to trigger panic | Set: `--panic-button-cc-value <int>` |
| **Session Settings** |
| `last_set` | `string \| null` | `null` | Last loaded set name (auto-updated) | Set: `--last-set <name>` |
| `auto_save` | `bool` | `true` | Auto-save changes to sets | Set: `--auto-save <true\|false>` |

## Managing Configuration

### CLI Commands

The `config` command provides a complete interface for managing configuration:

#### View Configuration

```bash
# Show all configuration values (default)
launchsampler config

# Show specific field
launchsampler config --field default_buffer_size
```

#### Set Configuration Values

```bash
# Set one field
launchsampler config set -b 256

# Set multiple fields at once
launchsampler config set -a 3 -b 256 --auto-save false
```

#### Validate Configuration

```bash
# Validate entire configuration with detailed report
launchsampler config validate

# Validate specific fields
launchsampler config validate default_audio_device default_buffer_size

# Output shows [OK] or [FAIL] with type information
```

Example output:
```
[OK] default_audio_device         Optional        = None
    Default audio output device ID
[OK] default_buffer_size          int             = 512
    Default audio buffer size in frames
```

#### Reset Configuration

```bash
# Reset all fields to defaults (prompts for confirmation)
launchsampler config reset

# Reset specific fields
launchsampler config reset default_buffer_size midi_poll_interval

# Skip confirmation prompt
launchsampler config reset default_buffer_size --yes
```

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

| Command | Log Level | Log File | Use Case |
|---------|-----------|----------|----------|
| `launchsampler` | WARNING | `~/.launchsampler/logs/launchsampler.log` | Default - only warnings and errors are logged |
| `launchsampler -v` | INFO | `~/.launchsampler/logs/launchsampler.log` | Includes informational messages |
| `launchsampler -vv` | DEBUG | `~/.launchsampler/logs/launchsampler.log` | Includes detailed debug information |
| `launchsampler --debug` | DEBUG | `./launchsampler-debug.log` (current directory) | Troubleshooting - creates log file in current directory for easy access |
| `launchsampler --log-file ./my-session.log` | INFO (default) | Custom path specified | Recording specific sessions |
| `launchsampler --log-file ./session.log --log-level DEBUG` | DEBUG, INFO, WARNING, or ERROR | Custom path specified | Fine-tune logging detail for custom log files |

### Log Rotation

Logs are automatically rotated to prevent excessive disk usage:

- **Maximum file size:** 10 MB
- **Backup files kept:** 5
- **Files:** `launchsampler.log`, `launchsampler.log.1`, ..., `launchsampler.log.5`

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

