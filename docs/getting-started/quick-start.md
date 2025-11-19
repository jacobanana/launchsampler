# Quick Start

Get up and running with LaunchSampler in just a few minutes!

## 1. Launch the Application

```bash
launchsampler
```

The application will start in **Play Mode** with an empty set.

!!! tip "First Run"
    On first run, LaunchSampler creates a config file at `~/.launchsampler/config.json`

## 2. Switch to Edit Mode

Press ++e++ to switch to Edit Mode, where you can build your sample set.

```
┌───────────────────────────────────────────────┐
│ Edit Mode: Untitled Set                   │
├───────────────────────────────────────────────┤
│ [8x8 Grid]  │  Pad Details Panel          │
│             │  - Sample name              │
│             │  - Playback mode            │
│             │  - Volume                   │
│             │  - Move controls            │
└───────────────────────────────────────────────┘
```

## 3. Load Samples

### Option A: Load from Directory

Press ++ctrl+l++ to load all samples from a directory:

1. Navigate to your samples folder
2. Select the directory
3. LaunchSampler automatically assigns first 64 samples to pads

### Option B: Assign Individual Samples

1. Click a pad or use arrow keys to select it
2. Press ++b++ to browse for a sample
3. Select your audio file (WAV, MP3, FLAC, etc.)

## 4. Configure Pads

For each pad, you can configure:

### Playback Mode

Press number keys to set playback mode:

- ++1++ - **One-Shot**: Play sample once from start to end
- ++2++ - **Hold**: Play while pad is held, stop when released
- ++3++ - **Loop**: Loop continuously until the pad is released
- ++4++ - **Loop Toggle**: Toggle loop on/off with each press

### Sample name

- Set a name for your pad, defaults to file name

### Adjust Volume

- You can edit the volume with the volume field

### Test Playback

- Press the associated pad on your MIDI controller
- Or Press ++space++ to test the selected pad

## 5. Save Your Set

Press ++ctrl+s++ to save your set:

1. Choose a location (defaults to `~/.launchsampler/sets/`)
2. Enter a name for your set
3. Your set is saved as a `.json` file

## 6. Switch to Play Mode

Press ++p++ to switch to Play Mode for live performance:

- **MIDI Input**: Your Launchpad is now active - press pads to trigger samples
- **Keyboard Input**: You can still test pads with ++space++
- **No Editing**: Edit operations are disabled to prevent accidents during performance

## Common Workflows

### Organize Samples

Use directional operations to arrange your pads:

```
Alt + Arrow    : Duplicate pad in direction
Ctrl + Arrow   : Move pad in direction
C              : Copy pad
X              : Cut pad
V              : Paste pad
D              : Delete pad
```

### Set Management

```
Ctrl + O       : Open saved set
Ctrl + L       : Load from directory
Ctrl + S       : Save current set
```

### Navigation

```
Arrow Keys     : Navigate between pads (Edit Mode)
E              : Switch to Edit Mode
P              : Switch to Play Mode
Esc            : Stop all audio (Panic)
Ctrl + Q       : Quit application
```

## Example Session

Here's a typical workflow:

1. **Start in Edit Mode** - ++e++
2. **Load samples** - ++ctrl+l++ → Select "Drums" folder
3. **Configure pads**:
   - Pad 0 (Kick): One-shot (++1++)
   - Pad 1 (Snare): One-shot (++1++)
   - Pad 8 (Hi-hat): Loop (++3++)
   - Pad 16 (Bass): Hold (++2++)
4. **Test your set** - Select pads and press ++space++
5. **Save** - ++ctrl+s++ → Name it "Drums Kit"
6. **Perform** - ++p++ to switch to Play Mode

## Next Steps

- [Configuration Guide](configuration.md) - Customize audio/MIDI settings
- [User Guide](../user-guide/overview.md) - Learn all features in depth
- [Keyboard Shortcuts](../user-guide/keyboard-shortcuts.md) - Complete shortcut reference
