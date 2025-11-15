# TUI Keyboard Shortcuts Implementation Plan

## Overview
Add keyboard shortcuts for copy/cut/paste, duplicate, and move operations to the Textual TUI, integrating the new EditorService methods.

## Current State

### Existing Keybindings (app.py lines 44-62)
- **Mode**: `e` (edit), `p` (play)
- **File**: `ctrl+s` (save), `ctrl+o` (open), `ctrl+l` (load dir), `ctrl+q` (quit)
- **Edit**: `b` (browse), `c` (clear), `space` (test)
- **Modes**: `1-4` (playback modes)
- **Nav**: Arrow keys (navigate grid)

### New EditorService Methods Available
- `copy_pad(pad_index)` - Copy to clipboard
- `cut_pad(pad_index)` - Cut to clipboard
- `paste_pad(target_index, overwrite=False)` - Paste from clipboard
- `duplicate_pad(source, target, overwrite=False)` - Direct duplicate
- `move_pad(source, target, swap=False)` - Move/swap pads
- `clear_all()` - Clear all pads
- `clear_range(start, end)` - Clear range
- `has_clipboard` property - Check clipboard state

---

## Implementation Plan

### Phase 1: Basic Clipboard Operations

#### 1.1 Copy/Cut/Paste (Standard Shortcuts)

**Location**: `app.py`, add to BINDINGS after line 62

```python
Binding("ctrl+c", "copy_pad", "Copy", show=True),
Binding("ctrl+x", "cut_pad", "Cut", show=True),
Binding("ctrl+v", "paste_pad", "Paste", show=True),
```

**Action Methods**: Add to LaunchpadSampler class

```python
def action_copy_pad(self) -> None:
    """Copy selected pad to clipboard."""
    if self._sampler_mode != "edit":
        return

    selected_pad = self.editor.selected_pad_index
    if selected_pad is None:
        self.notify("No pad selected", severity="warning")
        return

    try:
        pad = self.editor.copy_pad(selected_pad)
        self.notify(f"Copied: {pad.sample.name}", severity="information")
    except ValueError as e:
        self.notify(str(e), severity="error")

def action_cut_pad(self) -> None:
    """Cut selected pad to clipboard."""
    if self._sampler_mode != "edit":
        return

    selected_pad = self.editor.selected_pad_index
    if selected_pad is None:
        self.notify("No pad selected", severity="warning")
        return

    try:
        pad = self.editor.cut_pad(selected_pad)
        # Update UI - pad is now empty
        self._sync_pad_ui(selected_pad, self.editor.get_pad(selected_pad))
        self.notify(f"Cut: {pad.sample.name}", severity="information")
    except ValueError as e:
        self.notify(str(e), severity="error")

def action_paste_pad(self) -> None:
    """Paste clipboard to selected pad."""
    if self._sampler_mode != "edit":
        return

    selected_pad = self.editor.selected_pad_index
    if selected_pad is None:
        self.notify("No pad selected", severity="warning")
        return

    if not self.editor.has_clipboard:
        self.notify("Clipboard is empty", severity="warning")
        return

    try:
        # Try paste with overwrite=False first
        pad = self.editor.paste_pad(selected_pad, overwrite=False)
        self._reload_pad(selected_pad)
        self._sync_pad_ui(selected_pad, pad)
        self.notify(f"Pasted: {pad.sample.name}", severity="information")
    except ValueError as e:
        # Target occupied - show confirmation modal
        if "already has sample" in str(e):
            self._show_paste_confirmation(selected_pad)
        else:
            self.notify(str(e), severity="error")

def _show_paste_confirmation(self, target_index: int) -> None:
    """Show confirmation modal for overwrite paste."""
    from launchsampler.tui.widgets.paste_confirmation_modal import PasteConfirmationModal

    target_pad = self.editor.get_pad(target_index)
    modal = PasteConfirmationModal(
        target_index=target_index,
        current_sample=target_pad.sample.name
    )

    def handle_paste_choice(overwrite: bool) -> None:
        if overwrite:
            try:
                pad = self.editor.paste_pad(target_index, overwrite=True)
                self._reload_pad(target_index)
                self._sync_pad_ui(target_index, pad)
                self.notify(f"Pasted: {pad.sample.name}", severity="information")
            except ValueError as e:
                self.notify(str(e), severity="error")

    modal.on_confirm = handle_paste_choice
    self.push_screen(modal)
```

**New Widget Needed**: `paste_confirmation_modal.py`
- Similar to existing `move_confirmation_modal.py`
- Shows target pad's current sample name
- "Overwrite" / "Cancel" buttons

---

### Phase 2: Directional Operations

#### 2.1 Alt+Arrow: Duplicate in Direction

**Location**: `app.py`, add to BINDINGS

```python
Binding("alt+up", "duplicate_up", "Duplicate Up", show=False),
Binding("alt+down", "duplicate_down", "Duplicate Down", show=False),
Binding("alt+left", "duplicate_left", "Duplicate Left", show=False),
Binding("alt+right", "duplicate_right", "Duplicate Right", show=False),
```

**Helper Method**: Calculate target from direction

```python
def _get_directional_target(self, source_index: int, direction: str) -> Optional[int]:
    """Get target pad index from source + direction."""
    x, y = self.current_set.launchpad.note_to_xy(source_index)

    if direction == "up":
        y = max(0, y - 1)
    elif direction == "down":
        y = min(7, y + 1)
    elif direction == "left":
        x = max(0, x - 1)
    elif direction == "right":
        x = min(7, x + 1)

    target = self.current_set.launchpad.xy_to_note(x, y)
    return target if target != source_index else None
```

**Action Methods**:

```python
def action_duplicate_up(self) -> None:
    self._duplicate_directional("up")

def action_duplicate_down(self) -> None:
    self._duplicate_directional("down")

def action_duplicate_left(self) -> None:
    self._duplicate_directional("left")

def action_duplicate_right(self) -> None:
    self._duplicate_directional("right")

def _duplicate_directional(self, direction: str) -> None:
    """Duplicate pad in given direction."""
    if self._sampler_mode != "edit":
        return

    selected_pad = self.editor.selected_pad_index
    if selected_pad is None:
        self.notify("No pad selected", severity="warning")
        return

    target_index = self._get_directional_target(selected_pad, direction)
    if target_index is None:
        self.notify("Already at edge", severity="warning")
        return

    try:
        # Try duplicate with overwrite=False first
        pad = self.editor.duplicate_pad(selected_pad, target_index, overwrite=False)
        self._reload_pad(target_index)
        self._sync_pad_ui(target_index, pad)
        # Move selection to duplicated pad
        self.editor.select_pad(target_index)
        self._refresh_pad_ui()
        self.notify(f"Duplicated {direction}", severity="information")
    except ValueError as e:
        # Target occupied - show confirmation
        if "already has sample" in str(e):
            self._show_duplicate_confirmation(selected_pad, target_index, direction)
        else:
            self.notify(str(e), severity="error")
```

#### 2.2 Ctrl+Arrow: Move in Direction

**Location**: `app.py`, modify existing arrow bindings

**Current arrow bindings** (lines 58-61):
```python
Binding("up", "move_selection_up", "Move Up", show=False),
Binding("down", "move_selection_down", "Move Down", show=False),
```

**New bindings**:
```python
Binding("ctrl+up", "move_up", "Move Up", show=False),
Binding("ctrl+down", "move_down", "Move Down", show=False),
Binding("ctrl+left", "move_left", "Move Left", show=False),
Binding("ctrl+right", "move_right", "Move Right", show=False),
```

**Action Methods**:

```python
def action_move_up(self) -> None:
    self._move_directional("up")

def action_move_down(self) -> None:
    self._move_directional("down")

def action_move_left(self) -> None:
    self._move_directional("left")

def action_move_right(self) -> None:
    self._move_directional("right")

def _move_directional(self, direction: str) -> None:
    """Move pad in given direction."""
    if self._sampler_mode != "edit":
        return

    selected_pad = self.editor.selected_pad_index
    if selected_pad is None:
        self.notify("No pad selected", severity="warning")
        return

    target_index = self._get_directional_target(selected_pad, direction)
    if target_index is None:
        self.notify("Already at edge", severity="warning")
        return

    target_pad = self.editor.get_pad(target_index)

    # If target is occupied, show swap confirmation
    if target_pad.is_assigned:
        self._show_move_confirmation(selected_pad, target_index, direction)
    else:
        # Move to empty target
        try:
            source_pad, target_pad = self.editor.move_pad(selected_pad, target_index, swap=False)
            self._reload_pad(selected_pad)
            self._reload_pad(target_index)
            self._sync_pad_ui(selected_pad, source_pad)
            self._sync_pad_ui(target_index, target_pad)
            # Move selection to new location
            self.editor.select_pad(target_index)
            self._refresh_pad_ui()
            self.notify(f"Moved {direction}", severity="information")
        except ValueError as e:
            self.notify(str(e), severity="error")

def _show_move_confirmation(self, source: int, target: int, direction: str) -> None:
    """Show confirmation for move to occupied pad."""
    # Reuse existing MoveConfirmationModal or extend it
    # Add direction context to the modal
    # Offer: "Move" (overwrite), "Swap", "Cancel"
    pass
```

---

### Phase 3: Bulk Operations

#### 3.1 Clear All Pads

**Binding**:
```python
Binding("ctrl+shift+c", "clear_all_pads", "Clear All", show=True),
```

**Action Method**:

```python
def action_clear_all_pads(self) -> None:
    """Clear all pads with confirmation."""
    if self._sampler_mode != "edit":
        return

    # Show confirmation modal
    from launchsampler.tui.widgets.clear_all_confirmation_modal import ClearAllConfirmationModal

    modal = ClearAllConfirmationModal()

    def handle_confirm(confirmed: bool) -> None:
        if confirmed:
            count = self.editor.clear_all()
            # Reload all pads in audio engine
            for i in range(self.editor.grid_size):
                self._reload_pad(i)
            # Refresh entire UI
            self._refresh_pad_ui()
            self.notify(f"Cleared {count} pads", severity="information")

    modal.on_confirm = handle_confirm
    self.push_screen(modal)
```

#### 3.2 Clear Range (Optional - Advanced)

Could add visual selection mode:
- `Shift+Arrow` - Extend selection
- `Ctrl+Shift+X` - Clear selected range

---

## Implementation Checklist

### Files to Modify

- [ ] **`src/launchsampler/tui/app.py`**
  - [ ] Add new bindings to BINDINGS list
  - [ ] Implement `action_copy_pad()`
  - [ ] Implement `action_cut_pad()`
  - [ ] Implement `action_paste_pad()`
  - [ ] Implement `action_duplicate_up/down/left/right()`
  - [ ] Implement `action_move_up/down/left/right()`
  - [ ] Implement `action_clear_all_pads()`
  - [ ] Add helper `_get_directional_target()`
  - [ ] Add helper `_duplicate_directional()`
  - [ ] Add helper `_move_directional()`
  - [ ] Add helper `_show_paste_confirmation()`

### New Files to Create

- [ ] **`src/launchsampler/tui/widgets/paste_confirmation_modal.py`**
  - Similar to `move_confirmation_modal.py`
  - Shows current target sample name
  - "Overwrite" / "Cancel" buttons

- [ ] **`src/launchsampler/tui/widgets/duplicate_confirmation_modal.py`**
  - Shows direction and target info
  - "Overwrite" / "Cancel" buttons

- [ ] **`src/launchsampler/tui/widgets/clear_all_confirmation_modal.py`**
  - Shows count of assigned pads
  - "Clear All" / "Cancel" buttons

### Testing Plan

#### Manual Testing Scenarios

1. **Copy/Paste**
   - [ ] Copy assigned pad, paste to empty pad
   - [ ] Copy assigned pad, paste to occupied pad (confirm overwrite)
   - [ ] Try paste with empty clipboard (error message)
   - [ ] Copy, paste multiple times (clipboard persistence)

2. **Cut/Paste**
   - [ ] Cut assigned pad (source becomes empty)
   - [ ] Paste cut pad to new location
   - [ ] Verify source pad is empty, target has sample

3. **Duplicate Directional**
   - [ ] Alt+Up/Down/Left/Right to empty adjacent pad
   - [ ] Alt+Arrow to occupied adjacent pad (confirm overwrite)
   - [ ] Alt+Arrow at grid edge (error message)
   - [ ] Verify selection moves to duplicated pad

4. **Move Directional**
   - [ ] Ctrl+Up/Down/Left/Right to empty adjacent pad
   - [ ] Ctrl+Arrow to occupied pad (swap confirmation)
   - [ ] Verify source becomes empty, target has sample
   - [ ] Verify selection moves to new location

5. **Clear All**
   - [ ] Clear all with some pads assigned
   - [ ] Verify confirmation modal shows
   - [ ] Verify all pads cleared
   - [ ] Verify count message is correct

6. **Edge Cases**
   - [ ] Operations when no pad selected
   - [ ] Operations in play mode (should be ignored)
   - [ ] Clipboard persists across operations
   - [ ] UI updates correctly for all operations

---

## UI/UX Considerations

### Visual Feedback

1. **Clipboard Indicator**
   - Add clipboard status to status bar
   - Show "📋 [sample name]" when clipboard has content
   - Update on copy/cut operations

2. **Selection Highlighting**
   - Current selection should be visually distinct
   - Consider showing "ghost" preview for directional operations

3. **Confirmation Modals**
   - Keep consistent with existing modal style
   - Show relevant context (sample names, direction, count)
   - Clear action buttons

### Keyboard Shortcut Display

Update help text / keybinding footer to show:
- "Ctrl+C Copy" / "Ctrl+X Cut" / "Ctrl+V Paste"
- "Alt+↑↓←→ Duplicate" / "Ctrl+↑↓←→ Move"
- "Ctrl+Shift+C Clear All"

---

## Priority Order

### Phase 1 - Core Clipboard (MVP)
1. Copy/Cut/Paste (Ctrl+C/X/V)
2. Paste confirmation modal
3. Basic UI feedback

### Phase 2 - Directional Operations
1. Duplicate directional (Alt+Arrow)
2. Move directional (Ctrl+Arrow)
3. Confirmation modals for occupied targets

### Phase 3 - Bulk Operations
1. Clear all (Ctrl+Shift+C)
2. Clear all confirmation modal

### Phase 4 - Polish
1. Clipboard indicator in status bar
2. Improved visual feedback
3. Help documentation updates

---

## Notes

- All operations should only work in **edit mode**
- Check `self._sampler_mode != "edit"` at start of each action
- Always provide user feedback via `self.notify()`
- Handle exceptions gracefully with error messages
- Keep consistency with existing UI patterns
- Maintain separation: app.py (UI) → editor_service.py (logic)
- All modals should follow existing pattern (see `move_confirmation_modal.py`)
