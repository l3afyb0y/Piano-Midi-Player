# UI Refactor Notes

## Goals
- Make primary tasks faster to reach: play, record, load MIDI, switch synth backend.
- Keep the piano roll central while preserving quick access to routing/status controls.
- Introduce configurable workspace behavior (without introducing a heavy docking system).

## Research Signals Used
- DAW workflows favor persistent, user-adjustable workspaces and keyboard-first transport flow.
- Browser/library panes are expected to support fast filtering for large collections.
- Falling-note tools emphasize clear mode selection and simple device/sound routing controls.

## Implemented Shape
- Added shared synth mode constants in `piano_player/synth_modes.py` to avoid UI/controller drift.
- Added workspace preset model in `gui/workspace.py`:
  - `Balanced`
  - `Practice Focus`
  - `Library Focus`
- `gui/main_window.py` now includes:
  - menu-first workflow: `File` / `Synth` / `Metronome` / `Settings` / `View`
  - moved Open/Save/library refresh into `File`
  - moved synth backend/instrument/instrument-file actions into `Synth`
  - moved metronome + count-in controls into `Metronome`
  - moved routing/output/volume/workspace controls into `Settings`
  - Persistent UI state (splitter sizes, workspace selection, library filter)
  - MIDI library filter + sort controls for large collections
  - DAW-style transport shortcuts (`Space`, `R`, `M`, `Ctrl+O`, `Ctrl+S`)
  - Transport icon buttons and explicit transport-state badge
  - Piano-roll view window controls (slider + `Ctrl+Wheel` zoom)
  - MIDI library empty-state messaging and sort controls (A-Z / Z-A / recent)
  - Semantic button variants (`transport`, `record`, `toggle`) for coherent state color meaning
  - Status badges with explicit active/inactive coloring for routing + transport glanceability
- `piano_player/config.py` now uses bounded (non-recursive) soundfont scanning to avoid startup slowdown with large SFZ packs.

## Why This Direction
- Menus reduce visual clutter and keep the piano roll as the primary visual target.
- Presets provide configuration without complex drag-dock UX.
- Persisted layout avoids repeated setup on every launch.
- Shared synth mode definitions reduce regression risk during future UI/audio backend changes.
- The faster soundfont scan keeps startup and mode switching responsive even with heavy sample directories.
- Cohesive state colors and focus outlines improve readability and keyboard usability without adding UI clutter.
