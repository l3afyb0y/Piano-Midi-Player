# Piano MIDI Player

Desktop piano/MIDI app for low-latency live play, recording, MIDI editing, and falling-note practice on Linux.

## What It Does
- Routes live USB MIDI keyboard input to software synth output (headphones/system output)
- Supports built-in synth and optional SoundFont synthesis (FluidSynth)
- Includes instrument selection with `Piano` and `Guitar` presets
- Loads, edits, and saves MIDI files in a piano-roll editor
- Records MIDI + WAV audio with count-in and timeline seeking
- Shows falling notes and an 88-key keyboard visualization
- Includes a MIDI library browser with drag/drop import
- Provides a vertically resizable piano-roll area for focused practice/editing

## Current Defaults
- MIDI library folder defaults to `~/.config/piano-player/MIDI`
- Existing users with MIDI files in `~/midi` are auto-migrated logically (folder preserved unless changed in app settings)

## Requirements
- Python 3.10+
- PortAudio (`sounddevice` backend)
- Optional: FluidSynth + `.sf2` SoundFont
- Optional: USB MIDI keyboard/device

## Install

### Arch Linux / AUR-style source build
From the repo root:
```bash
makepkg -si
```
Or via helper wrapper:
```bash
bash scripts/install_arch.sh
```
For local dev package testing:
```bash
bash scripts/install_arch.sh --dev
```
Or directly:
```bash
cd dev && makepkg -si
```

This uses `PKGBUILD` and installs:
- `/usr/bin/piano-player`
- `/usr/share/applications/piano-player.desktop`
- `/usr/share/icons/hicolor/scalable/apps/piano-player.svg`

Note:
- `sounddevice` is currently distributed on Arch via AUR (`python-sounddevice`) rather than official repos.
- If audio backend import fails at runtime, install it with an AUR helper or:
```bash
python -m pip install --user sounddevice
```

### Other Linux distros
```bash
bash scripts/install_linux.sh
```

## Run
```bash
python main.py
```

## SoundFont Setup
You can provide an `.sf2` by:
- placing it in `soundfonts/`
- setting `PIANO_PLAYER_SOUNDFONT` (or `SOUNDFONT_PATH`)
- using **Load SoundFont...** inside the app

If no SoundFont is available, Piano Player uses the built-in simple synth.

## Self-Test
```bash
python scripts/self_test.py --list-midi --load-soundfont
```
Optional flags: `--beep`, `--list-devices`, `--timeout 10`

## MIDI Editing
- **Open MIDI...** to load `.mid`/`.midi`
- Double-click to add notes
- Right-click/Delete to remove notes
- Drag notes to move, drag top edge to resize
- Box-select for multi-note edits
- **Save MIDI...** to export edits

## Recording Flow
- Enable **Count-in** for pre-roll timing
- Press **Record** to capture live MIDI + WAV
- Playback/seek from the timeline slider
- Save captured WAV or MIDI from recording controls
- Sustain pedal events are recorded and applied during playback/editing

## Project Layout
- `main.py`: lightweight application entrypoint
- `piano_player/`: app controller, config, service layer
- `audio/`: audio engine, synth backends, metronome
- `midi/`: MIDI input parser/handler + recorder
- `gui/`: Qt window + piano roll/keyboard widgets + theme
- `recording/`: WAV writer
- `scripts/`: install, build, launch, self-test
- `docs/`: build notes + design plans

## Build
See `docs/BUILD.md`.

## Packaging Note
When app launch/metadata changes, update both:
- `piano-player.desktop`
- `PKGBUILD`
- `dev/PKGBUILD`

After updating `PKGBUILD`, regenerate AUR metadata:
```bash
makepkg --printsrcinfo > .SRCINFO
```

## Troubleshooting
- No audio output: verify PortAudio and available output devices
- No MIDI input ports: reconnect keyboard or check ALSA/JACK routing
- SoundFont not loading: verify FluidSynth is installed and `.sf2` path is valid
- Crackle/dropouts on some systems: try a larger audio buffer, e.g. `PIANO_PLAYER_BUFFER_SIZE=512 python main.py`
- If your system is tuned for realtime audio, you can still force lower latency explicitly: `PIANO_PLAYER_AUDIO_LATENCY=low python main.py`
