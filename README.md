# Piano MIDI Player

Desktop piano/MIDI app for low-latency live play, recording, MIDI editing, and falling-note practice on Linux.

## What It Does
- Routes live USB MIDI keyboard input to software synth output (headphones/system output)
- Supports built-in synth and optional sampled synthesis:
  - SF2 SoundFont via FluidSynth
  - SFZ instrument files via sfizz
- Includes instrument selection with `Acoustic Grand Piano` and `Clean Electric Guitar` presets
- Loads, edits, and saves MIDI files in a piano-roll editor
- Records MIDI + WAV audio with count-in and timeline seeking
- Shows falling notes and an 88-key keyboard visualization
- Includes a MIDI library browser with drag/drop import
- Uses a menu-first control model (`File`, `Synth`, `Metronome`, `Settings`) to keep the piano roll as the dominant workspace
- Provides a vertically resizable piano-roll area for focused practice/editing
- Adds DAW-style workspace presets (`Balanced`, `Practice Focus`, `Library Focus`) with persistent layout
- Adds MIDI library filtering/sorting, piano-roll view zoom, and core shortcuts (`Space` play/stop, `R` record, `M` metronome, `Ctrl+O`, `Ctrl+S`)

## Current Defaults
- MIDI library folder defaults to `~/.config/piano-player/MIDI`
- Synth backend defaults to `SFZ (sfizz)` and automatically falls back to `SF2 (FluidSynth)` when no usable SFZ file is available
- Existing users with MIDI files in `~/midi` are auto-migrated logically (folder preserved unless changed in app settings)

## Requirements
- Python 3.10+
- PortAudio (`sounddevice` backend)
- Optional: FluidSynth + `.sf2`
- Optional: sfizz (`libsfizz`) + `.sfz`
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
By default this installer now also attempts to install system audio dependencies
(`fluidsynth` + `sfizz`) using your distro package manager.
The Linux installer downloads two default high-quality instrument packs (SFZ):
- Acoustic Grand Piano: Salamander Grand Piano (CC-BY-3.0)
- Clean Electric Guitar: FSBS bridge clean (CC0)
Total download is large (about 825 MiB), by design for quality.
To skip that step:
```bash
bash scripts/install_linux.sh --no-default-soundfonts
```
To skip system dependency installation:
```bash
bash scripts/install_linux.sh --no-system-audio-deps
```

## Run
```bash
python main.py
```

## Sampled Instrument Setup
You can provide an `.sf2` or `.sfz` by:
- placing it in `soundfonts/`
- setting one of:
  - `PIANO_PLAYER_SOUNDFONT`
  - `PIANO_PLAYER_SFZ`
  - `SOUNDFONT_PATH`
- setting per-instrument overrides:
  - `PIANO_PLAYER_SOUNDFONT_PIANO`
  - `PIANO_PLAYER_SOUNDFONT_GUITAR`
  - `PIANO_PLAYER_SFZ_PIANO`
  - `PIANO_PLAYER_SFZ_GUITAR`
- using **Load \<Instrument> Instrument File...** inside the app

Default bundled/fetched presets:
- `Acoustic Grand Piano`: `SalamanderGrandPiano-V3+20200602.sfz` (FreePats, CC-BY-3.0)
- `Clean Electric Guitar`: `EGuitarFSBS-bridge-clean-20220911.sfz` (FreePats, CC0)

To manually fetch/update those defaults in a source checkout:
```bash
bash scripts/download_default_soundfonts.sh
```

Instrument file selection is per instrument. For example, you can load one `.sf2/.sfz` for
`Acoustic Grand Piano` and a different `.sf2/.sfz` for `Clean Electric Guitar`; each is remembered independently.
The `Synth` menu includes:
- explicit backend selection:
  - `Simple Synth`
  - `SF2 (FluidSynth)` for `.sf2` files
  - `SFZ (sfizz)` for `.sfz` files
- a per-instrument preset dropdown (`Auto` + discovered `.sf2`/`.sfz` files)
- **Load \<Instrument> Instrument File...** for bringing in custom files

The `Metronome` menu includes:
- metronome enable/disable
- quick BPM adjust (`+/-1`) and BPM presets
- count-in enable/disable and beats selection

When you switch synth backend, the instrument-file dropdown is filtered to matching file types for that backend.

## Workspace and Navigation
- Use **View** or **Settings > Workspace** presets to reflow the layout.
- Layout and library filter state are persisted across launches.
- MIDI Library supports quick text filtering for large song collections.
- Piano Roll supports adjustable view window (`View` slider) and `Ctrl+MouseWheel` zoom.
- MIDI input, audio output, and volume controls are in the `Settings` menu.

Redistribution note:
- only ship bundled instruments you are licensed to redistribute
- include license/attribution text for each bundled instrument in your distribution/docs
- default curated set mixes CC-BY-3.0 (piano) + CC0 (guitar), with attribution files installed

## Licensing
- Project code: `MIT` (`LICENSE`)
- Bundled default instruments: `CC-BY-3.0` (Salamander piano) + `CC0-1.0` (FSBS clean electric guitar)
- Third-party summary: `THIRD_PARTY_LICENSES.md`

Optional runtime dependencies such as FluidSynth/pyFluidSynth/sfizz keep their own
upstream licenses and are installed as separate system packages.

If no compatible instrument file is available, Piano Player uses the built-in simple synth.

## Self-Test
```bash
python scripts/self_test.py --list-midi --load-soundfont
```
Optional flags: `--beep`, `--list-devices`, `--timeout 10`

## MIDI Editing
- `File > Open MIDI...` to load `.mid`/`.midi`
- Double-click to add notes
- Right-click/Delete to remove notes
- Drag notes to move, drag top edge to resize
- Box-select for multi-note edits
- `File > Save MIDI...` to export edits

## Recording Flow
- Enable count-in from the `Metronome` menu for pre-roll timing
- Press **Record** to capture live MIDI + WAV
- Playback/seek from the timeline slider
- Save captured WAV or MIDI from `File` menu or recording controls
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
- Instrument file not loading:
  - for `.sf2`: verify FluidSynth + `pyfluidsynth` are installed
  - for `.sfz`: verify `sfizz`/`sfizz-lib` are installed
- Crackle/dropouts on some systems: try a larger audio buffer, e.g. `PIANO_PLAYER_BUFFER_SIZE=512 python main.py`
- If your system is tuned for realtime audio, you can still force lower latency explicitly: `PIANO_PLAYER_AUDIO_LATENCY=low python main.py`
