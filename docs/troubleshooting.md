# Troubleshooting

This guide helps you resolve common issues with LaunchSampler.

## Logging and Diagnostics

### Enabling Debug Logging

When troubleshooting issues, enable debug logging to capture detailed information:

```bash
launchsampler --debug
```

This creates `launchsampler-debug.log` in your current directory with detailed diagnostic information.

For more information about logging options, see the [Logging section in Configuration](getting-started/configuration.md#logging).

---

### Permission Errors (Linux)

On Linux, you may need to add your user to the `audio` group:

```bash
sudo usermod -a -G audio $USER
```

Then log out and log back in for changes to take effect.


## Audio Issues

### Audio Dropouts / Glitches

**Symptoms:** Crackling, popping, or stuttering audio during playback.

**Solutions:**

1. **Increase buffer size:**

   ```bash
   launchsampler config --buffer-size 1024
   ```

2. **Close other audio applications** that might be competing for the audio device

3. **Use a dedicated audio interface** if using built-in audio

4. **Check CPU usage** - ensure other processes aren't consuming too much CPU

### High Latency

**Symptoms:** Noticeable delay between pressing a pad and hearing the sample.

**Solutions:**

1. **Decrease buffer size** (if your system can handle it):
   ```bash
   launchsampler config --buffer-size 32
   ```

2. **Use a better audio API:**
   - **Windows:** ASIO > WASAPI > DirectSound > MME
   - **macOS:** CoreAudio (default)
   - **Linux:** ALSA > PulseAudio

3. **Update audio drivers** to the latest version

4. **Use a dedicated audio interface** with ASIO support (Windows)

### No Audio Output

**Symptoms:** No sound when triggering samples.

**Solutions:**

1. **Verify sample files exist** and are valid audio files. When a file can't be loaded, it will be shown as unavailable.

2. **Revert to default audio device:**
   ```bash
   launchsampler config --audio-device default
   ```

3. **Check system volume** and ensure LaunchSampler isn't muted

4. **Try a different audio device:**
   By default, the `audio list` command will only show low latency devices, you can see the full list with:
   ```bash
   launchsampler audio list --all
   ```
   Choose a different device ID

5. **Check logs for errors:**
   ```bash
   launchsampler --debug
   cat launchsampler-debug.log | grep ERROR
   ```

### Wrong Audio Device

**Symptoms:** Audio plays through wrong output (e.g., speakers instead of headphones).

**Solutions:**

1. **List available devices:**
   ```bash
   launchsampler audio list
   ```

2. **Set device explicitly in config:**
   ```bash
   launchsampler config --audio-device 3
   ```

3. **Restart LaunchSampler** after changing config

### Audio Device Unavailable / Changed

**Symptoms:** Configured audio device is no longer available (e.g., external interface unplugged, device ID changed).

**Automatic Fallback Behavior:**

LaunchSampler automatically handles invalid or unavailable audio devices with the following fallback sequence:

1. **Tries configured device** (`default_audio_device` in config.json)
2. **Falls back to OS default** if configured device is invalid
3. **Searches for any low-latency device** if OS default doesn't support low-latency APIs
4. **Shows error** only if NO valid low-latency devices are found

### Audio Device Already in Use

**Symptoms:** Application fails to start with error:
```
Error opening OutputStream: Invalid device [PaErrorCode -9996]
```

**Cause:** The audio device is currently in use by another application or instance of LaunchSampler.

**Solutions:**

1. **Check for running instances:**
   - Close any other running instances of LaunchSampler
   - Check task manager/activity monitor for multiple processes

2. **Close other audio applications:**
   - Close DAWs, music players, or other audio software
   - Check system tray for hidden audio applications

3. **Restart audio services (if needed):**

   === "Windows"
       ```powershell
       # Restart Windows Audio service
       net stop audiosrv && net start audiosrv
       ```

   === "macOS"
       ```bash
       # Restart CoreAudio
       sudo killall coreaudiod
       ```

   === "Linux"
       ```bash
       # Kill processes using audio device
       sudo fuser -k /dev/snd/*

       # Or restart PulseAudio
       pulseaudio -k && pulseaudio --start
       ```

4. **Try a different audio device:**
   ```bash
   launchsampler audio list
   launchsampler config --audio-device <different-device-id>
   ```

5. **Reboot your computer** to release all audio device locks

---

## MIDI Issues

### MIDI Device Not Detected

**Symptoms:** Launchpad not recognized or not showing in device list.

**Solutions:**

1. **Check USB connection:**
   - Ensure cable is properly connected
   - Try a different USB port
   - Try a different USB cable

2. **List MIDI devices:**
   ```bash
   launchsampler midi list
   ```

3. **Install manufacturer drivers:**
   - Download latest drivers from Novation website
   - Restart computer after installation

4. **Check device permissions (Linux):**
   ```bash
   sudo usermod -a -G audio $USER
   # Log out and log back in
   ```

5. **Verify device works in other software** (e.g., DAW, Launchpad Arcade)

### MIDI Notes Not Triggering Samples

**Symptoms:** Pressing Launchpad pads doesn't trigger samples in Play Mode.

**Solutions:**

1. **Ensure you're in Play Mode:**
   - Press ++p++ to switch to Play Mode
   - Look for "Play Mode" in the status bar

2. **Check that pads have samples assigned:**
   - Switch to Edit Mode (++e++)
   - Verify pads show sample information

3. **Monitor MIDI input:**
   ```bash
   launchsampler midi monitor
   ```
   Press pads - you should see MIDI messages

4. **Check MIDI routing:**
   - Ensure no other application is capturing MIDI
   - Close DAWs or other MIDI software

5. **Enable debug logging:**
   ```bash
   launchsampler --debug
   ```
   Check for MIDI-related errors

### Launchpad LEDs Not Updating

**Symptoms:** Launchpad LEDs don't light up or don't reflect pad states.

**Solutions:**


1. **Check Launchpad mode:**
   - Some Launchpads have different modes
   - Ensure it's in "Programmer" or "Live" mode
   - Refer to your Launchpad's manual

2. **Verify MIDI output connection:**
   ```bash
   launchsampler midi list
   ```
   Check that MIDI output port is detected

3. **Reset Launchpad:**
   - Disconnect and reconnect USB
   - Power cycle if battery-powered

4. **Check logs for LED errors:**
   ```bash
   launchsampler --debug
   grep -i "led" launchsampler-debug.log
   ```

---

## Application Issues

### Application Won't Start

**Symptoms:** LaunchSampler crashes or exits immediately on startup.

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version  # Should be 3.12 or higher
   ```

2. **Enable debug logging:**
   ```bash
   launchsampler --debug 2>&1 | tee startup-error.log
   ```

3. **Verify installation:**
   ```bash
   launchsampler --version
   ```

4. **Reinstall dependencies:**
   ```bash
   # If using pipx
   pipx reinstall launchsampler

   # If using uv
   cd launchsampler
   uv sync --reinstall
   ```

5. **Check for conflicting packages:**
   ```bash
   pip list | grep -i midi
   pip list | grep -i audio
   ```

6. **Try with minimal config:**
   ```bash
   # Backup existing config
   mv ~/.launchsampler/config.json ~/.launchsampler/config.json.bak

   # Start with defaults
   launchsampler
   ```

### TUI Display Issues

**Symptoms:** Garbled text, incorrect colors, or layout problems in the terminal.

**Solutions:**

1. **Use a modern terminal:**
   - **Windows:** Windows Terminal (recommended)
   - **macOS:** iTerm2 or Terminal.app
   - **Linux:** gnome-terminal, kitty, alacritty

2. **Check terminal size:**
   - Ensure terminal is at least 80x24 characters
   - Resize terminal window

3. **Set correct locale:**
   ```bash
   export LANG=en_US.UTF-8
   export LC_ALL=en_US.UTF-8
   ```

4. **Try a different terminal emulator**

5. **Check terminal color support:**
   ```bash
   echo $COLORTERM  # Should show "truecolor" or similar
   ```

### Application Freezes or Becomes Unresponsive

**Symptoms:** LaunchSampler stops responding to input.

**Solutions:**

1. **Force quit:**
   - Press ++ctrl+c++ in terminal
   - Or press ++ctrl+q++ in the TUI

2. **Check CPU usage:**
   ```bash
   # In another terminal
   top -p $(pgrep -f launchsampler)
   ```

3. **Check for blocking operations:**
   ```bash
   launchsampler --debug
   # Look for operations that take too long
   ```

4. **Reduce sample count:**
   - Use fewer simultaneous samples
   - Reduce sample file sizes

5. **Increase buffer size** to reduce CPU load:
   ```json
   {
     "default_buffer_size": 1024
   }
   ```

### Samples Not Loading

**Symptoms:** Error when loading samples from directory or set file.

**Solutions:**

1. **Check file permissions:**
   ```bash
   ls -l /path/to/samples/
   ```
   Ensure files are readable

2. **Verify file formats:**
   - Supported: WAV, MP3, FLAC, OGG, AIFF
   - Check file extensions match actual format

3. **Check file paths:**
   - Use absolute paths
   - Ensure no special characters in paths
   - Avoid spaces in filenames (or use quotes)

4. **Verify sample directory exists:**
   ```bash
   launchsampler --samples-dir /path/to/samples --debug
   ```

5. **Check disk space:**
   ```bash
   df -h
   ```

6. **Look for loading errors in logs:**
   ```bash
   grep -i "load" launchsampler-debug.log
   grep -i "sample" launchsampler-debug.log
   ```

---

## Configuration Issues

### Config File Not Found

**Symptoms:** LaunchSampler can't find or load config file.

**Solutions:**

1. **Check config location:**

   === "Linux / macOS"
       ```bash
       ls -la ~/.launchsampler/config.json
       ```

   === "Windows"
       ```powershell
       dir %USERPROFILE%\.launchsampler\config.json
       ```

2. **Create config directory:**
   ```bash
   mkdir -p ~/.launchsampler
   ```

3. **Let LaunchSampler create default config:**
   ```bash
   launchsampler
   # Will auto-create config.json
   ```

4. **Manually create config:**
   ```bash
   echo '{"default_buffer_size": 512}' > ~/.launchsampler/config.json
   ```

### Invalid Config Values

**Symptoms:** Config validation errors on startup.

**Solutions:**

1. **Validate JSON syntax:**
   ```bash
   python -m json.tool ~/.launchsampler/config.json
   ```

2. **Reset to defaults:**
   ```bash
   rm ~/.launchsampler/config.json
   launchsampler  # Will create new default config
   ```

3. **Check value ranges:**
   - `default_buffer_size`: 128, 256, 512, 1024, or 2048
   - `default_audio_device`: Valid device ID from `launchsampler audio list`
   - `midi_poll_interval`: Any positive float (typically 0.5 to 5.0 seconds)

4. **Review config documentation:**
   See [Configuration Guide](getting-started/configuration.md) for all valid options

---

## Logging Issues

For logging-specific troubleshooting (log files not created, empty logs, etc.), see the [Logging Troubleshooting](getting-started/configuration.md#logging-troubleshooting) section in the Configuration guide.

---

## Performance Issues

### High CPU Usage

**Symptoms:** LaunchSampler consumes excessive CPU resources.

**Solutions:**

1. **Increase buffer size:**
   ```json
   {
     "default_buffer_size": 1024
   }
   ```

2. **Reduce simultaneous voices:**
   - Use one-shot mode instead of loop
   - Limit number of playing samples

3. **Close other applications**

4. **Check for debug logging:**
   - Disable verbose logging in production
   - Use default logging level (WARNING)

### Slow Sample Loading

**Symptoms:** Long delay when loading sets or samples.

**Solutions:**

1. **Use smaller sample files:**
   - Convert to lower bit depth (16-bit instead of 24-bit)
   - Use compressed formats (MP3, OGG) for non-critical samples

2. **Reduce sample count:**
   - Split large sets into multiple smaller sets
   - Load only needed samples

3. **Use SSD instead of HDD** for sample storage

4. **Check disk I/O:**
   ```bash
   # Linux
   iostat -x 1

   # macOS
   iostat -w 1
   ```

---

## Platform-Specific Issues

### Windows

#### ASIO4ALL Not Working

**Problem:** ASIO4ALL driver not recognized.

**Solutions:**

1. **Install ASIO4ALL:**
   - Download from http://www.asio4all.org/
   - Run installer as administrator

2. **Configure ASIO4ALL:**
   - Open ASIO4ALL control panel
   - Enable your audio device
   - Set buffer size

3. **Set in LaunchSampler config:**
   ```json
   {
     
     "default_audio_device": 0
   }
   ```

#### Permission Errors

**Problem:** Access denied errors when accessing files or devices.

**Solutions:**

1. **Run as administrator** (only if necessary)

2. **Check file permissions** in Windows Explorer

3. **Use user-writable locations:**
   ```powershell
   launchsampler --log-file %USERPROFILE%\Desktop\launchsampler.log
   ```

### macOS

#### CoreAudio Issues

**Problem:** Audio device not accessible or permission errors.

**Solutions:**

1. **Grant microphone permission:**
   - System Preferences → Security & Privacy → Microphone
   - Enable for Terminal or your terminal app

2. **Reset Core Audio:**
   ```bash
   sudo killall coreaudiod
   ```

3. **Check audio MIDI setup:**
   - Open Audio MIDI Setup.app
   - Verify device is recognized

### Linux

#### ALSA Errors

**Problem:** "Device or resource busy" errors.

**Solutions:**

1. **Add user to audio group:**
   ```bash
   sudo usermod -a -G audio $USER
   # Log out and log back in
   ```

2. **Kill processes using audio device:**
   ```bash
   sudo fuser -k /dev/snd/*
   ```

3. **Use PulseAudio plugin:**
   ```bash
   sudo apt-get install pulseaudio-utils
   ```

4. **Check ALSA configuration:**
   ```bash
   cat /proc/asound/cards
   aplay -l
   ```

#### PulseAudio Issues

**Problem:** No audio with PulseAudio.

**Solutions:**

1. **Restart PulseAudio:**
   ```bash
   pulseaudio -k
   pulseaudio --start
   ```

2. **Check PulseAudio devices:**
   ```bash
   pacmd list-sinks
   ```

3. **Set default sink:**
   ```bash
   pactl set-default-sink <sink-name>
   ```

---

## Getting Help

If you can't resolve your issue:

1. **Enable debug logging:**
   ```bash
   launchsampler --debug
   ```

2. **Gather system information:**
   ```bash
   launchsampler --version
   python --version
   uname -a  # Linux/macOS
   ```

3. **Check existing issues:**
   - [GitHub Issues](https://github.com/jacobanana/launchsampler/issues)

4. **Create a new issue:**
   - Include debug log (relevant portions)
   - System information
   - Steps to reproduce
   - Expected vs actual behavior

5. **Join the community:**
   - [GitHub Discussions](https://github.com/jacobanana/launchsampler/discussions)

---

## Related Documentation

- [Configuration Guide](getting-started/configuration.md) - Detailed config options and logging
- [Installation](getting-started/installation.md) - Install and verify setup
- [User Guide](user-guide/overview.md) - Learn how to use LaunchSampler
