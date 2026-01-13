# Piano MIDI Player

Desktop piano/MIDI player with real-time input, synth playback, recording, and visualization.

## Features
- Real-time MIDI input with keyboard and piano roll visualization
- Two synth engines: Simple Synth (built-in) and SoundFont (FluidSynth)
- Metronome with adjustable BPM
- Record to WAV and MIDI, with playback and timeline seek

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

## Project layout
- `main.py`: app entry point
- `audio/`: audio engine and synths
- `gui/`: Qt UI and visualizations
- `midi/`: MIDI input and recording
- `recording/`: WAV recorder

## Troubleshooting
- No audio output: confirm an output device is available and PortAudio is installed.
- No MIDI ports: connect a device or install a virtual MIDI driver.
