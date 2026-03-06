# Piano Player

Linux desktop app for live MIDI piano play, recording, editing, and falling-note practice.

## Features
- Live USB MIDI input to audio output (headphones/speakers)
- Three synth backends:
  - `SFZ (sfizz)`
  - `SF2 (FluidSynth)`
  - `Simple Synth` (built-in fallback)
- Instrument presets:
  - `Acoustic Grand Piano`
  - `Clean Electric Guitar`
- MIDI import/edit/save in a piano-roll editor
- WAV and MIDI recording
- Falling-note view with 88-key keyboard visualization
- MIDI library browser with filtering/sorting
- Built-in metronome with BPM and count-in controls

## Installation

### Arch Linux
From repository root:

```bash
makepkg -si
```

Or:

```bash
bash scripts/install_arch.sh
```

### Other Linux distros

```bash
bash scripts/install_linux.sh
```

Optional installer flags:

```bash
bash scripts/install_linux.sh --no-default-soundfonts
bash scripts/install_linux.sh --no-system-audio-deps
```

## Run

```bash
python main.py
```

If installed through package/launcher, run `piano-player` from your app menu or terminal.

## Defaults
- MIDI library folder: `~/.config/piano-player/MIDI`
- Preferred sampled backend: `SFZ (sfizz)` when available
- Fallback sampled backend: `SF2 (FluidSynth)` when SFZ is unavailable
- Final fallback: built-in `Simple Synth`

## Soundfont / Instrument Files
You can use your own `.sfz` and `.sf2` files.

Ways to load files:
- `Synth` menu -> load per-instrument file
- Place files in `soundfonts/`
- Set environment variables:
  - `PIANO_PLAYER_SFZ`
  - `PIANO_PLAYER_SOUNDFONT`
  - `SOUNDFONT_PATH`
  - Per-instrument overrides:
    - `PIANO_PLAYER_SFZ_PIANO`
    - `PIANO_PLAYER_SFZ_GUITAR`
    - `PIANO_PLAYER_SOUNDFONT_PIANO`
    - `PIANO_PLAYER_SOUNDFONT_GUITAR`

To fetch the default bundled-quality instrument sets in a source checkout:

```bash
bash scripts/download_default_soundfonts.sh
```

## MIDI Editing Quick Start
- `File > Open MIDI...`
- Double-click piano roll to add a note
- Right-click/Delete selected notes to remove
- Drag notes to move/resize
- `File > Save MIDI...`

## Troubleshooting
- No audio:
  - Verify output device in `Settings`
  - Ensure `python-sounddevice` and `portaudio` are installed
- SF2 not loading:
  - Install `fluidsynth` and `python-pyfluidsynth`
- SFZ not loading:
  - Install `sfizz` (`sfizz-lib` on Arch)
- Crackle/dropouts:
  - Increase buffer size:

```bash
PIANO_PLAYER_BUFFER_SIZE=512 python main.py
```

  - Or force low-latency profile:

```bash
PIANO_PLAYER_AUDIO_LATENCY=low python main.py
```

## Licensing
- Project code: `MIT` (`LICENSE`)
- Bundled instruments include `CC-BY-3.0` and `CC0-1.0`
- Third-party/license summary: `THIRD_PARTY_LICENSES.md`
