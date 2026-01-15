# Piano MIDI Player

Desktop piano/MIDI player with real-time input, synth playback, recording, and visualization.

## Features
- Load MIDI files and visualize them as falling notes
- Add notes (double-click) and remove notes (right-click or Delete) for quick transcription edits
- Drag notes to move them, drag the top edge to resize, and box-select for multi-editing
- MIDI library list from a configurable folder (defaults to `~/midi`) with drag-and-drop import
- Real-time MIDI input with keyboard and piano roll visualization
- Two synth engines: Simple Synth (built-in) and SoundFont (FluidSynth)
- Metronome with adjustable BPM
- Record to WAV and MIDI with count-in and timeline seek

## Requirements
- Python 3.10+
- PortAudio (for `sounddevice`)
- Optional: FluidSynth library + a `.sf2` SoundFont for realistic piano sound
- Optional: MIDI input device

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux one-command setup (creates `.venv`, installs deps, installs desktop entry):
```bash
bash scripts/install.sh
```
System-wide desktop entry (requires sudo):
```bash
bash scripts/install.sh --system
```

### System dependencies (optional but recommended)
Linux (Debian/Ubuntu):
```bash
sudo apt-get install portaudio19-dev fluidsynth
```

macOS:
```bash
brew install portaudio fluid-synth
```

## SoundFont setup
SoundFonts are optional. If you have a `.sf2` file, you can:
- Place it in `soundfonts/` (ignored by git), or
- Set `PIANO_PLAYER_SOUNDFONT` (or `SOUNDFONT_PATH`) to the file path, or
- Use the "Load SoundFont..." button in the app.

If none are found, the app falls back to the built-in Simple Synth.

## Run
```bash
python main.py
```

## Self-test
Run quick dependency/device checks from the repo root:
```bash
python scripts/self_test.py --list-midi --load-soundfont
```
Optional flags: `--beep`, `--list-devices`, `--timeout 10`.

## MIDI editing
- Open a `.mid` or `.midi` file with the **Open MIDI...** button.
- Double-click in the piano roll to add a note.
- Right-click a note (or select it and press Delete) to remove it.
- Click-drag notes to move them; drag the top edge to resize.
- Drag a box to multi-select notes.
- Use the **Grid**/**Snap** controls above the piano roll to align edits to the beat.
- Use **Save MIDI...** to export the edited result.
- Recording starts at the current timeline position and merges into the piano roll.

## Recording (DAW-style)
- Enable **Count-in** to get a pre-roll before recording (uses the metronome BPM).
- If a MIDI is loaded and not playing, recording auto-starts playback for overdub timing.
- Stop ends recording and merges new notes into the piano roll.

## MIDI library
- On first launch the app creates `~/midi` if it doesn't exist.
- Use **Set MIDI Folder...** to point the library to a different directory.
- Drag `.mid`/`.midi` files onto the app to move them into the library folder.

## Build app
See `docs/BUILD.md` for PyInstaller build steps.

## Desktop launcher (Linux)
`pip install -r requirements.txt` only installs Python deps; it does not install a desktop entry.
Run the installer to create a launcher that rebuilds the app when sources change:
```bash
bash scripts/install_desktop.sh
```
This installs `piano-player.desktop` to `~/.local/share/applications` so rofi and other launchers can see it.
It also installs the app icon to the hicolor theme for launchers that show icons.
System-wide install (requires sudo):
```bash
bash scripts/install_desktop.sh --system
```
System-wide installs use `/usr/local/bin` and `/usr/local/share/applications`.

## Docs
See `docs/README.md` for build and design references.

## Project layout
- `main.py`: app entry point
- `audio/`: audio engine and synths
- `gui/`: Qt UI and visualizations
- `midi/`: MIDI input and recording
- `recording/`: WAV recorder

## Troubleshooting
- No audio output: confirm an output device is available and PortAudio is installed.
- No MIDI ports: connect a device or install a virtual MIDI driver.
