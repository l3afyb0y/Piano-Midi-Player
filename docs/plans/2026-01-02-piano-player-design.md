# Piano Player Design

**Date:** 2026-01-02
**Status:** Approved

## Overview

A Python application that accepts MIDI input from a Casio CDP-130 keyboard and outputs synthesized audio through PipeWire to wireless headphones. Provides a PyQt6 GUI with volume control, sustain pedal support, and recording capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PyQt6 GUI                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │
│  │ Volume   │  │ Synth    │  │ Record Controls          │  │
│  │ Slider   │  │ Selector │  │ [●Rec] [■Stop] [Save]    │  │
│  └──────────┘  └──────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
┌─────────────────┐                   ┌─────────────────┐
│  MIDI Thread    │                   │  Audio Thread   │
│  (rtmidi)       │───Note Events────▶│  (sounddevice)  │
│  CDP-130 input  │                   │  PipeWire out   │
└─────────────────┘                   └─────────────────┘
         │                                     │
         ▼                                     ▼
┌─────────────────┐                   ┌─────────────────┐
│  MIDI Recorder  │                   │  WAV Recorder   │
│  (mido)         │                   │  (wave module)  │
└─────────────────┘                   └─────────────────┘
```

### Key Decisions

- Separate threads for MIDI input and audio output to minimize latency
- `rtmidi` for MIDI (reliable, low-latency)
- `sounddevice` for audio (works great with PipeWire)
- Qt signals connect threads safely to the GUI

## Sound Synthesis

### Simple Synthesizer (default)

- Generates audio mathematically using additive synthesis
- Multiple sine waves at harmonic frequencies create a piano-like timbre
- ADSR envelope (Attack-Decay-Sustain-Release) shapes each note
- Polyphonic - can play multiple notes simultaneously
- Sustain pedal holds notes until released

### SoundFont Synthesizer (optional)

- Uses `fluidsynth` library via Python bindings (`pyfluidsynth`)
- Load any `.sf2` soundfont file
- Much more realistic sound but requires external file
- Can switch between synths at runtime via dropdown

### Latency Target

Under 20ms from keypress to sound (achievable with small audio buffer ~256-512 samples at 44.1kHz)

## GUI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  🎹 Piano Player                                    [─][□][×]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Audio ──────────────────┐  ┌─ Synthesizer ───────────┐ │
│  │ Volume: ════════●══ 80%  │  │ [▼ Simple Synth      ]  │ │
│  │                          │  │ [Load SoundFont...]     │ │
│  └──────────────────────────┘  └─────────────────────────┘ │
│                                                             │
│  ┌─ Recording ──────────────────────────────────────────┐  │
│  │  [● Record]  [■ Stop]  │  00:00  │  [Save WAV] [MIDI] │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Status ─────────────────────────────────────────────┐  │
│  │  MIDI: CASIO USB-MIDI ✓    Audio: PipeWire ✓         │  │
│  │  Sustain: ○ Off            Notes active: 3           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### GUI Elements

- **Volume slider** - Real-time gain adjustment (0-100%)
- **Synth dropdown** - Switch between Simple/SoundFont
- **Load SoundFont button** - File picker for `.sf2` files
- **Record/Stop** - Toggle recording with elapsed time display
- **Save buttons** - Export recording as WAV (audio) or MIDI (notes)
- **Status bar** - Shows connection state, sustain pedal, active note count

## Project Structure

```
piano-player/
├── main.py                 # Entry point, launches GUI
├── gui/
│   ├── __init__.py
│   ├── main_window.py      # PyQt main window
│   └── widgets.py          # Custom UI components
├── audio/
│   ├── __init__.py
│   ├── engine.py           # Audio thread, mixing, output
│   ├── simple_synth.py     # Mathematical synthesizer
│   └── soundfont_synth.py  # FluidSynth wrapper
├── midi/
│   ├── __init__.py
│   ├── input.py            # MIDI input thread
│   └── recorder.py         # MIDI file recording
├── recording/
│   ├── __init__.py
│   └── wav_recorder.py     # WAV file recording
└── requirements.txt
```

## Dependencies

### System packages (pacman)

```bash
sudo pacman -S fluidsynth python-numpy python-pyqt6
```

### AUR packages (yay)

```bash
yay -S python-python-rtmidi python-sounddevice python-mido python-pyfluidsynth
```

### Alternative: Virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install PyQt6 python-rtmidi sounddevice numpy mido pyfluidsynth
```

## Features

| Feature | Description |
|---------|-------------|
| Volume control | Real-time gain adjustment 0-100% |
| Sustain pedal | Hold notes when pedal pressed (CC64) |
| WAV recording | Save audio output to WAV file |
| MIDI recording | Save note events to MIDI file |
| Simple synth | Additive synthesis, no external files |
| SoundFont synth | Load .sf2 files for realistic sound |

## Hardware

- **Keyboard:** Casio CDP-130 (connects via USB-MIDI)
- **Audio output:** PipeWire → wireless headphones
