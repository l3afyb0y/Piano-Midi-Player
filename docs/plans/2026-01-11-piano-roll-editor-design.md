# Piano Roll Editor Design

Replaces the falling notes visualization with a full DAW-style piano roll editor.

## Overview

- **Unified view**: Single `PianoRollWidget` handles both visualization and editing
- **Vertical orientation**: Time flows top-to-bottom (preserves falling notes aesthetic)
- **Bottom keyboard**: Existing keyboard widget provides visual feedback
- **Flexible grid**: Supports both musical (beat-based) and time-based grids

## Data Model

Uses existing dataclasses:
- `NoteEvent`: note, start_time, duration, velocity
- `SustainEvent`: time, on

New dataclass:
- `UndoAction`: captures state changes for undo/redo

## Widget State

```python
events: list[NoteEvent]
sustain_events: list[SustainEvent]
selected_indices: set[int]
undo_stack: list[UndoAction]
redo_stack: list[UndoAction]
snap_enabled: bool
grid_mode: Literal["musical", "time"]
bpm: float  # default 120
grid_division: float  # 1/4, 1/8 for musical; 0.25s, 0.5s for time
playhead_time: float
pixels_per_second: float  # zoom level
```

## Coordinate System

- **Y-axis**: Time (0 at top, increasing downward)
- **X-axis**: Pitch (mapped to piano keys)
- View scrolls vertically; zoom adjusts pixels_per_second
- During playback, view auto-scrolls to follow playhead

## Interaction Patterns

### Selection
- Click: select single note (clears previous)
- Ctrl+Click: add/remove from selection
- Drag on empty: box-select
- Ctrl+A: select all
- Escape: clear selection

### Moving Notes
- Drag selected notes to reposition
- Shift+drag: constrain to one axis
- Respects snap-to-grid when enabled

### Resizing Notes
- Drag top edge: change start time
- Drag bottom edge: change duration
- Respects snap-to-grid

### Drawing Notes
- Double-click on empty area: create note
- Default duration: one grid unit (or 0.25s if snap off)
- Default velocity: 100

### Deleting
- Delete or Backspace: remove selected notes

## Editing Operations

### Velocity
- Mouse wheel on selection: adjust ±5 per tick
- Right-click → "Set Velocity...": dialog with slider (0-127)

### Quantize
- Ctrl+Q or right-click → "Quantize"
- Snaps start times to nearest grid line
- Option to quantize end times

### Split/Join
- S: split note at playhead position
- J: join adjacent notes on same pitch

### Undo/Redo
- Ctrl+Z: undo
- Ctrl+Shift+Z or Ctrl+Y: redo
- Tracks: creation, deletion, moves, resizes, velocity, quantize, split/join
- Stack depth: 50 actions

### Clipboard
- Ctrl+C: copy (stores relative positions)
- Ctrl+X: cut
- Ctrl+V: paste at playhead
- Pasted notes become new selection

## Grid System

### Musical Grid
- BPM setting (default 120)
- Divisions: 1/1, 1/2, 1/4, 1/8, 1/16, 1/32
- Stronger lines on downbeats

### Time Grid
- Divisions: 1s, 0.5s, 0.25s, 0.1s
- Fixed interval lines

### Snap
- Toggle via toolbar button or G key
- When on, all operations snap to grid

## Navigation

- Mouse wheel: scroll timeline
- Ctrl+wheel: zoom in/out (50-500 px/sec range)
- Shift+wheel: scroll pitches
- Click timeline gutter: seek playhead

## Toolbar Layout

```
[Play] [Stop] [Record] | [Snap: ON] [Grid: Musical] [1/4] [BPM: 120] | [Zoom: slider] | 00:00.0 / 02:34.5
```

## Context Menu

- Cut / Copy / Paste
- Delete
- Quantize...
- Set Velocity...
- Split at Playhead
- Join Notes

## Sustain Events

- Displayed as horizontal bars at grid bottom
- Selectable and movable
- Double-click to toggle on/off
- Distinct color (blue)

## Implementation

### Files

| File | Change |
|------|--------|
| `gui/piano_roll_widget.py` | New - main widget |
| `gui/main_window.py` | Use new widget, add toolbar |
| `main.py` | Update signal connections |
| `gui/falling_notes_widget.py` | Delete after migration |

### Class Structure

```
PianoRollWidget(QWidget)
├── PianoRollState
├── PianoRollRenderer
├── InteractionHandler
└── ClipboardManager
```

### Build Sequence

1. Basic rendering (notes + grid)
2. Selection and keyboard navigation
3. Drag-to-move and resize
4. Drawing new notes and deletion
5. Undo/redo system
6. Quantize, split/join, velocity editing
7. Clipboard operations
8. Sustain event editing
9. Toolbar integration and migration
10. Remove old FallingNotesWidget
