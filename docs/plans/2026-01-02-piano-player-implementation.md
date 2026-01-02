# Piano Player Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python application that receives MIDI input from a Casio CDP-130 keyboard and outputs synthesized piano audio through PipeWire.

**Architecture:** Multi-threaded design with separate MIDI input thread, audio output thread, and Qt GUI main thread. Note events flow from MIDI → Synthesizer → Audio buffer → Speakers. Qt signals safely bridge threads.

**Tech Stack:** Python 3, PyQt6, python-rtmidi, sounddevice, numpy, mido, pyfluidsynth

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `main.py`
- Create: `.gitignore`

**Step 1: Create requirements.txt**

```
PyQt6>=6.4.0
python-rtmidi>=1.5.0
sounddevice>=0.4.6
numpy>=1.24.0
mido>=1.3.0
pyfluidsynth>=1.3.0
```

**Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
*.sf2
recordings/
.idea/
*.egg-info/
```

**Step 3: Create minimal main.py**

```python
#!/usr/bin/env python3
"""Piano Player - MIDI to audio application."""

import sys

def main():
    print("Piano Player starting...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Verify it runs**

Run: `python main.py`
Expected: "Piano Player starting..."

**Step 5: Commit**

```bash
git add requirements.txt main.py .gitignore
git commit -m "feat: initial project setup"
```

---

## Task 2: Audio Engine Foundation

**Files:**
- Create: `audio/__init__.py`
- Create: `audio/engine.py`
- Create: `tests/__init__.py`
- Create: `tests/test_audio_engine.py`

**Step 1: Create directory structure**

```bash
mkdir -p audio tests
touch audio/__init__.py tests/__init__.py
```

**Step 2: Write failing test for AudioEngine**

Create `tests/test_audio_engine.py`:

```python
"""Tests for audio engine."""

import numpy as np
from audio.engine import AudioEngine


def test_audio_engine_initializes():
    """AudioEngine should initialize with default sample rate."""
    engine = AudioEngine()
    assert engine.sample_rate == 44100
    assert engine.buffer_size == 512


def test_audio_engine_generates_silence():
    """AudioEngine with no active notes should produce silence."""
    engine = AudioEngine()
    buffer = engine.generate_buffer()
    assert len(buffer) == 512
    assert np.allclose(buffer, 0.0)
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_audio_engine.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 4: Write minimal AudioEngine implementation**

Create `audio/engine.py`:

```python
"""Audio engine - generates and outputs audio buffers."""

import numpy as np


class AudioEngine:
    """Manages audio generation and output."""

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 512):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self._volume = 0.8

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))

    def generate_buffer(self) -> np.ndarray:
        """Generate next audio buffer. Returns silence when no notes active."""
        return np.zeros(self.buffer_size, dtype=np.float32)
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_audio_engine.py -v`
Expected: 2 passed

**Step 6: Commit**

```bash
git add audio/ tests/
git commit -m "feat: add AudioEngine foundation"
```

---

## Task 3: Simple Synthesizer - Single Note

**Files:**
- Create: `audio/simple_synth.py`
- Create: `tests/test_simple_synth.py`

**Step 1: Write failing test for SimpleSynth note generation**

Create `tests/test_simple_synth.py`:

```python
"""Tests for simple synthesizer."""

import numpy as np
from audio.simple_synth import SimpleSynth


def test_synth_generates_sound_for_active_note():
    """Synth should generate non-zero audio when note is active."""
    synth = SimpleSynth(sample_rate=44100)
    synth.note_on(60, velocity=100)  # Middle C
    buffer = synth.generate(512)
    assert len(buffer) == 512
    assert not np.allclose(buffer, 0.0), "Buffer should not be silent"


def test_synth_silent_with_no_notes():
    """Synth should generate silence when no notes active."""
    synth = SimpleSynth(sample_rate=44100)
    buffer = synth.generate(512)
    assert np.allclose(buffer, 0.0)


def test_synth_note_off_stops_sound():
    """Note off should eventually silence the note (after release)."""
    synth = SimpleSynth(sample_rate=44100)
    synth.note_on(60, velocity=100)
    synth.note_off(60)
    # Generate enough buffers to complete release envelope
    for _ in range(100):
        buffer = synth.generate(512)
    assert np.allclose(buffer, 0.0, atol=0.001)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_simple_synth.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write SimpleSynth implementation**

Create `audio/simple_synth.py`:

```python
"""Simple additive synthesizer with ADSR envelope."""

import numpy as np
from dataclasses import dataclass
from typing import Dict


@dataclass
class Note:
    """Active note state."""
    frequency: float
    velocity: float
    phase: float = 0.0
    envelope: float = 0.0
    stage: str = "attack"  # attack, decay, sustain, release, off
    released: bool = False


class SimpleSynth:
    """Additive synthesizer with piano-like timbre."""

    # ADSR envelope times in seconds
    ATTACK = 0.01
    DECAY = 0.1
    SUSTAIN_LEVEL = 0.7
    RELEASE = 0.3

    # Harmonic overtones for piano-like sound (frequency multiplier, amplitude)
    HARMONICS = [
        (1.0, 1.0),    # fundamental
        (2.0, 0.5),    # 2nd harmonic
        (3.0, 0.25),   # 3rd harmonic
        (4.0, 0.125),  # 4th harmonic
    ]

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._notes: Dict[int, Note] = {}

    def note_on(self, note_number: int, velocity: int):
        """Start playing a note."""
        frequency = 440.0 * (2.0 ** ((note_number - 69) / 12.0))
        self._notes[note_number] = Note(
            frequency=frequency,
            velocity=velocity / 127.0,
            phase=0.0,
            envelope=0.0,
            stage="attack",
            released=False,
        )

    def note_off(self, note_number: int):
        """Release a note."""
        if note_number in self._notes:
            self._notes[note_number].released = True
            self._notes[note_number].stage = "release"

    def generate(self, num_samples: int) -> np.ndarray:
        """Generate audio samples."""
        buffer = np.zeros(num_samples, dtype=np.float32)

        notes_to_remove = []

        for note_num, note in self._notes.items():
            note_buffer = self._generate_note(note, num_samples)
            buffer += note_buffer

            if note.stage == "off":
                notes_to_remove.append(note_num)

        for note_num in notes_to_remove:
            del self._notes[note_num]

        # Soft clip to prevent harsh distortion
        buffer = np.tanh(buffer)
        return buffer

    def _generate_note(self, note: Note, num_samples: int) -> np.ndarray:
        """Generate samples for a single note with envelope."""
        buffer = np.zeros(num_samples, dtype=np.float32)
        dt = 1.0 / self.sample_rate

        for i in range(num_samples):
            # Update envelope
            note.envelope = self._update_envelope(note, dt)

            if note.stage == "off":
                break

            # Generate harmonics
            sample = 0.0
            for harmonic_mult, harmonic_amp in self.HARMONICS:
                freq = note.frequency * harmonic_mult
                sample += harmonic_amp * np.sin(2 * np.pi * freq * note.phase)

            # Apply envelope and velocity
            sample *= note.envelope * note.velocity * 0.3
            buffer[i] = sample

            # Advance phase
            note.phase += dt

        return buffer

    def _update_envelope(self, note: Note, dt: float) -> float:
        """Update ADSR envelope, returns new envelope value."""
        if note.stage == "attack":
            note.envelope += dt / self.ATTACK
            if note.envelope >= 1.0:
                note.envelope = 1.0
                note.stage = "decay"
        elif note.stage == "decay":
            note.envelope -= dt / self.DECAY * (1.0 - self.SUSTAIN_LEVEL)
            if note.envelope <= self.SUSTAIN_LEVEL:
                note.envelope = self.SUSTAIN_LEVEL
                note.stage = "sustain"
        elif note.stage == "sustain":
            if note.released:
                note.stage = "release"
        elif note.stage == "release":
            note.envelope -= dt / self.RELEASE * self.SUSTAIN_LEVEL
            if note.envelope <= 0.0:
                note.envelope = 0.0
                note.stage = "off"

        return note.envelope
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_simple_synth.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add audio/simple_synth.py tests/test_simple_synth.py
git commit -m "feat: add SimpleSynth with ADSR envelope"
```

---

## Task 4: MIDI Input Handler

**Files:**
- Create: `midi/__init__.py`
- Create: `midi/input.py`
- Create: `tests/test_midi_input.py`

**Step 1: Create midi package**

```bash
mkdir -p midi
touch midi/__init__.py
```

**Step 2: Write failing test for MIDI parsing**

Create `tests/test_midi_input.py`:

```python
"""Tests for MIDI input handling."""

from midi.input import MidiMessage, parse_midi_message


def test_parse_note_on():
    """Parse note on message."""
    msg = parse_midi_message([0x90, 60, 100])  # Note on, middle C, velocity 100
    assert msg.type == "note_on"
    assert msg.note == 60
    assert msg.velocity == 100


def test_parse_note_off():
    """Parse note off message."""
    msg = parse_midi_message([0x80, 60, 0])  # Note off, middle C
    assert msg.type == "note_off"
    assert msg.note == 60


def test_parse_note_on_zero_velocity_is_note_off():
    """Note on with velocity 0 should be treated as note off."""
    msg = parse_midi_message([0x90, 60, 0])
    assert msg.type == "note_off"
    assert msg.note == 60


def test_parse_sustain_pedal_on():
    """Parse sustain pedal on (CC64 >= 64)."""
    msg = parse_midi_message([0xB0, 64, 127])  # CC64, value 127
    assert msg.type == "sustain"
    assert msg.value is True


def test_parse_sustain_pedal_off():
    """Parse sustain pedal off (CC64 < 64)."""
    msg = parse_midi_message([0xB0, 64, 0])  # CC64, value 0
    assert msg.type == "sustain"
    assert msg.value is False
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_midi_input.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 4: Write MIDI input implementation**

Create `midi/input.py`:

```python
"""MIDI input handling and parsing."""

from dataclasses import dataclass
from typing import Optional, Any, List, Callable
import threading


@dataclass
class MidiMessage:
    """Parsed MIDI message."""
    type: str  # note_on, note_off, sustain, unknown
    note: Optional[int] = None
    velocity: Optional[int] = None
    value: Optional[Any] = None


def parse_midi_message(data: List[int]) -> MidiMessage:
    """Parse raw MIDI bytes into a MidiMessage."""
    if len(data) < 1:
        return MidiMessage(type="unknown")

    status = data[0] & 0xF0  # Ignore channel

    if status == 0x90 and len(data) >= 3:  # Note On
        note, velocity = data[1], data[2]
        if velocity == 0:
            return MidiMessage(type="note_off", note=note)
        return MidiMessage(type="note_on", note=note, velocity=velocity)

    elif status == 0x80 and len(data) >= 3:  # Note Off
        note = data[1]
        return MidiMessage(type="note_off", note=note)

    elif status == 0xB0 and len(data) >= 3:  # Control Change
        cc_num, cc_val = data[1], data[2]
        if cc_num == 64:  # Sustain pedal
            return MidiMessage(type="sustain", value=(cc_val >= 64))

    return MidiMessage(type="unknown")


class MidiInputThread(threading.Thread):
    """Thread that reads MIDI input and emits callbacks."""

    def __init__(self, port_name: Optional[str] = None):
        super().__init__(daemon=True)
        self._port_name = port_name
        self._running = False
        self._callbacks: List[Callable[[MidiMessage], None]] = []
        self._midi_in = None

    def add_callback(self, callback: Callable[[MidiMessage], None]):
        """Register callback for MIDI messages."""
        self._callbacks.append(callback)

    def run(self):
        """Main thread loop - reads MIDI and dispatches callbacks."""
        import rtmidi

        self._midi_in = rtmidi.MidiIn()

        # Find and open port
        ports = self._midi_in.get_ports()
        port_index = None

        if self._port_name:
            for i, name in enumerate(ports):
                if self._port_name.lower() in name.lower():
                    port_index = i
                    break
        elif ports:
            # Auto-select first non-through port
            for i, name in enumerate(ports):
                if "through" not in name.lower():
                    port_index = i
                    break
            if port_index is None and ports:
                port_index = 0

        if port_index is None:
            print("No MIDI ports available")
            return

        self._midi_in.open_port(port_index)
        print(f"Opened MIDI port: {ports[port_index]}")

        self._running = True
        while self._running:
            msg = self._midi_in.get_message()
            if msg:
                data, _ = msg
                parsed = parse_midi_message(data)
                for callback in self._callbacks:
                    callback(parsed)

    def stop(self):
        """Stop the MIDI input thread."""
        self._running = False
        if self._midi_in:
            self._midi_in.close_port()

    @staticmethod
    def list_ports() -> List[str]:
        """List available MIDI input ports."""
        import rtmidi
        midi_in = rtmidi.MidiIn()
        return midi_in.get_ports()
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_midi_input.py -v`
Expected: 5 passed

**Step 6: Commit**

```bash
git add midi/ tests/test_midi_input.py
git commit -m "feat: add MIDI input parsing and thread"
```

---

## Task 5: Sustain Pedal Support in Synth

**Files:**
- Modify: `audio/simple_synth.py`
- Modify: `tests/test_simple_synth.py`

**Step 1: Add failing test for sustain**

Add to `tests/test_simple_synth.py`:

```python
def test_sustain_holds_released_notes():
    """Sustain pedal should hold notes that are released."""
    synth = SimpleSynth(sample_rate=44100)
    synth.sustain_on()
    synth.note_on(60, velocity=100)
    synth.note_off(60)
    # Generate a few buffers - note should still be audible
    for _ in range(10):
        buffer = synth.generate(512)
    assert not np.allclose(buffer, 0.0), "Note should sustain"


def test_sustain_off_releases_held_notes():
    """Releasing sustain should release all held notes."""
    synth = SimpleSynth(sample_rate=44100)
    synth.sustain_on()
    synth.note_on(60, velocity=100)
    synth.note_off(60)
    synth.sustain_off()
    # Generate enough buffers for release
    for _ in range(100):
        buffer = synth.generate(512)
    assert np.allclose(buffer, 0.0, atol=0.001)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_simple_synth.py::test_sustain_holds_released_notes -v`
Expected: FAIL with AttributeError

**Step 3: Update SimpleSynth with sustain support**

Update `audio/simple_synth.py` - add to `__init__`:

```python
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._notes: Dict[int, Note] = {}
        self._sustain = False
        self._sustained_notes: set = set()  # Notes held by sustain pedal
```

Add new methods:

```python
    def sustain_on(self):
        """Enable sustain pedal."""
        self._sustain = True

    def sustain_off(self):
        """Disable sustain pedal and release held notes."""
        self._sustain = False
        for note_num in self._sustained_notes:
            if note_num in self._notes:
                self._notes[note_num].released = True
                self._notes[note_num].stage = "release"
        self._sustained_notes.clear()
```

Update `note_off` method:

```python
    def note_off(self, note_number: int):
        """Release a note (or hold if sustain is on)."""
        if note_number in self._notes:
            if self._sustain:
                self._sustained_notes.add(note_number)
            else:
                self._notes[note_number].released = True
                self._notes[note_number].stage = "release"
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_simple_synth.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add audio/simple_synth.py tests/test_simple_synth.py
git commit -m "feat: add sustain pedal support to SimpleSynth"
```

---

## Task 6: WAV Recorder

**Files:**
- Create: `recording/__init__.py`
- Create: `recording/wav_recorder.py`
- Create: `tests/test_wav_recorder.py`

**Step 1: Create recording package**

```bash
mkdir -p recording
touch recording/__init__.py
```

**Step 2: Write failing test for WAV recorder**

Create `tests/test_wav_recorder.py`:

```python
"""Tests for WAV recorder."""

import os
import tempfile
import wave
import numpy as np
from recording.wav_recorder import WavRecorder


def test_wav_recorder_creates_file():
    """WavRecorder should create a valid WAV file."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    try:
        recorder = WavRecorder(path, sample_rate=44100)
        recorder.start()
        # Write some audio data
        samples = np.sin(np.linspace(0, 2*np.pi, 1024)).astype(np.float32)
        recorder.write(samples)
        recorder.stop()

        # Verify file exists and is valid
        assert os.path.exists(path)
        with wave.open(path, 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            assert wf.getnframes() == 1024
    finally:
        os.unlink(path)


def test_wav_recorder_duration():
    """WavRecorder should track recording duration."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    try:
        recorder = WavRecorder(path, sample_rate=44100)
        recorder.start()
        # Write 1 second of audio (44100 samples)
        for _ in range(86):  # 86 * 512 ≈ 44032 samples
            recorder.write(np.zeros(512, dtype=np.float32))
        recorder.stop()

        assert abs(recorder.duration - 1.0) < 0.02  # Within 20ms
    finally:
        os.unlink(path)
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_wav_recorder.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 4: Write WavRecorder implementation**

Create `recording/wav_recorder.py`:

```python
"""WAV file recording."""

import wave
import numpy as np
from typing import Optional


class WavRecorder:
    """Records audio to a WAV file."""

    def __init__(self, path: str, sample_rate: int = 44100, channels: int = 1):
        self._path = path
        self._sample_rate = sample_rate
        self._channels = channels
        self._wav_file: Optional[wave.Wave_write] = None
        self._frames_written = 0

    def start(self):
        """Start recording."""
        self._wav_file = wave.open(self._path, 'wb')
        self._wav_file.setnchannels(self._channels)
        self._wav_file.setsampwidth(2)  # 16-bit
        self._wav_file.setframerate(self._sample_rate)
        self._frames_written = 0

    def write(self, samples: np.ndarray):
        """Write audio samples to file."""
        if self._wav_file is None:
            return

        # Convert float32 [-1, 1] to int16
        int_samples = (samples * 32767).astype(np.int16)
        self._wav_file.writeframes(int_samples.tobytes())
        self._frames_written += len(samples)

    def stop(self):
        """Stop recording and close file."""
        if self._wav_file:
            self._wav_file.close()
            self._wav_file = None

    @property
    def duration(self) -> float:
        """Return duration of recording in seconds."""
        return self._frames_written / self._sample_rate

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording."""
        return self._wav_file is not None
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_wav_recorder.py -v`
Expected: 2 passed

**Step 6: Commit**

```bash
git add recording/ tests/test_wav_recorder.py
git commit -m "feat: add WAV recorder"
```

---

## Task 7: MIDI Recorder

**Files:**
- Create: `midi/recorder.py`
- Create: `tests/test_midi_recorder.py`

**Step 1: Write failing test for MIDI recorder**

Create `tests/test_midi_recorder.py`:

```python
"""Tests for MIDI recorder."""

import os
import tempfile
import mido
from midi.recorder import MidiRecorder


def test_midi_recorder_creates_file():
    """MidiRecorder should create a valid MIDI file."""
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        path = f.name

    try:
        recorder = MidiRecorder()
        recorder.start()
        recorder.note_on(60, 100)
        recorder.note_off(60)
        recorder.save(path)

        # Verify file is valid MIDI
        assert os.path.exists(path)
        mid = mido.MidiFile(path)
        assert len(mid.tracks) >= 1
    finally:
        os.unlink(path)


def test_midi_recorder_captures_timing():
    """MidiRecorder should capture note timing."""
    recorder = MidiRecorder()
    recorder.start()
    recorder.note_on(60, 100)
    # Simulate some time passing
    import time
    time.sleep(0.1)
    recorder.note_off(60)

    events = recorder.get_events()
    assert len(events) >= 2
    assert events[0]['type'] == 'note_on'
    assert events[1]['type'] == 'note_off'
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_midi_recorder.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write MidiRecorder implementation**

Create `midi/recorder.py`:

```python
"""MIDI event recording."""

import time
import mido
from typing import List, Dict, Any, Optional


class MidiRecorder:
    """Records MIDI events with timing."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None
        self._recording = False

    def start(self):
        """Start recording."""
        self._events = []
        self._start_time = time.time()
        self._recording = True

    def stop(self):
        """Stop recording."""
        self._recording = False

    def note_on(self, note: int, velocity: int):
        """Record note on event."""
        if not self._recording:
            return
        self._events.append({
            'type': 'note_on',
            'note': note,
            'velocity': velocity,
            'time': time.time() - self._start_time,
        })

    def note_off(self, note: int):
        """Record note off event."""
        if not self._recording:
            return
        self._events.append({
            'type': 'note_off',
            'note': note,
            'velocity': 0,
            'time': time.time() - self._start_time,
        })

    def sustain(self, on: bool):
        """Record sustain pedal event."""
        if not self._recording:
            return
        self._events.append({
            'type': 'sustain',
            'value': on,
            'time': time.time() - self._start_time,
        })

    def get_events(self) -> List[Dict[str, Any]]:
        """Return recorded events."""
        return self._events.copy()

    def save(self, path: str):
        """Save recording to MIDI file."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Set tempo (120 BPM)
        track.append(mido.MetaMessage('set_tempo', tempo=500000))

        # Convert events to MIDI messages
        last_time = 0
        ticks_per_second = mid.ticks_per_beat * 2  # At 120 BPM

        for event in self._events:
            delta_seconds = event['time'] - last_time
            delta_ticks = int(delta_seconds * ticks_per_second)
            last_time = event['time']

            if event['type'] == 'note_on':
                track.append(mido.Message(
                    'note_on',
                    note=event['note'],
                    velocity=event['velocity'],
                    time=delta_ticks
                ))
            elif event['type'] == 'note_off':
                track.append(mido.Message(
                    'note_off',
                    note=event['note'],
                    velocity=0,
                    time=delta_ticks
                ))
            elif event['type'] == 'sustain':
                value = 127 if event['value'] else 0
                track.append(mido.Message(
                    'control_change',
                    control=64,
                    value=value,
                    time=delta_ticks
                ))

        mid.save(path)

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording."""
        return self._recording

    @property
    def duration(self) -> float:
        """Return duration of recording."""
        if not self._events:
            return 0.0
        return self._events[-1]['time']
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_midi_recorder.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add midi/recorder.py tests/test_midi_recorder.py
git commit -m "feat: add MIDI recorder"
```

---

## Task 8: Audio Output Thread

**Files:**
- Modify: `audio/engine.py`

**Step 1: Add audio output to AudioEngine**

Update `audio/engine.py`:

```python
"""Audio engine - generates and outputs audio buffers."""

import threading
import numpy as np
from typing import Optional, Protocol
import sounddevice as sd


class Synthesizer(Protocol):
    """Protocol for synthesizer implementations."""
    def generate(self, num_samples: int) -> np.ndarray: ...
    def note_on(self, note: int, velocity: int) -> None: ...
    def note_off(self, note: int) -> None: ...


class AudioEngine:
    """Manages audio generation and output."""

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 512):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self._volume = 0.8
        self._synth: Optional[Synthesizer] = None
        self._stream: Optional[sd.OutputStream] = None
        self._running = False
        self._lock = threading.Lock()
        self._audio_callback_fn = None

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))

    def set_synth(self, synth: Synthesizer):
        """Set the synthesizer to use."""
        with self._lock:
            self._synth = synth

    def set_audio_callback(self, callback):
        """Set callback to receive generated audio (for recording)."""
        self._audio_callback_fn = callback

    def _audio_callback(self, outdata, frames, time_info, status):
        """Sounddevice callback - runs in audio thread."""
        with self._lock:
            if self._synth:
                buffer = self._synth.generate(frames)
                buffer = buffer * self._volume
            else:
                buffer = np.zeros(frames, dtype=np.float32)

        outdata[:, 0] = buffer

        # Notify callback (for recording)
        if self._audio_callback_fn:
            self._audio_callback_fn(buffer)

    def start(self):
        """Start audio output."""
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=1,
            dtype=np.float32,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._running = True

    def stop(self):
        """Stop audio output."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def generate_buffer(self) -> np.ndarray:
        """Generate next audio buffer. For testing without output."""
        with self._lock:
            if self._synth:
                return self._synth.generate(self.buffer_size) * self._volume
            return np.zeros(self.buffer_size, dtype=np.float32)
```

**Step 2: Verify existing tests still pass**

Run: `python -m pytest tests/test_audio_engine.py -v`
Expected: 2 passed

**Step 3: Commit**

```bash
git add audio/engine.py
git commit -m "feat: add audio output streaming to AudioEngine"
```

---

## Task 9: PyQt6 Main Window

**Files:**
- Create: `gui/__init__.py`
- Create: `gui/main_window.py`

**Step 1: Create gui package**

```bash
mkdir -p gui
touch gui/__init__.py
```

**Step 2: Create main window**

Create `gui/main_window.py`:

```python
"""Main application window."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSlider, QLabel, QPushButton, QComboBox,
    QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals for thread-safe communication
    volume_changed = pyqtSignal(float)
    synth_changed = pyqtSignal(str)
    soundfont_loaded = pyqtSignal(str)
    record_toggled = pyqtSignal(bool)
    save_wav = pyqtSignal(str)
    save_midi = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Player")
        self.setMinimumSize(500, 300)

        self._recording = False
        self._record_time = 0

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """Create UI elements."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top row: Audio + Synthesizer
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        # Audio group
        audio_group = QGroupBox("Audio")
        audio_layout = QHBoxLayout(audio_group)

        audio_layout.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        audio_layout.addWidget(self._volume_slider)

        self._volume_label = QLabel("80%")
        self._volume_label.setMinimumWidth(40)
        audio_layout.addWidget(self._volume_label)

        top_row.addWidget(audio_group)

        # Synthesizer group
        synth_group = QGroupBox("Synthesizer")
        synth_layout = QVBoxLayout(synth_group)

        self._synth_combo = QComboBox()
        self._synth_combo.addItems(["Simple Synth", "SoundFont"])
        self._synth_combo.currentTextChanged.connect(self._on_synth_changed)
        synth_layout.addWidget(self._synth_combo)

        self._soundfont_btn = QPushButton("Load SoundFont...")
        self._soundfont_btn.clicked.connect(self._on_load_soundfont)
        self._soundfont_btn.setEnabled(False)
        synth_layout.addWidget(self._soundfont_btn)

        top_row.addWidget(synth_group)

        # Recording group
        record_group = QGroupBox("Recording")
        record_layout = QHBoxLayout(record_group)

        self._record_btn = QPushButton("● Record")
        self._record_btn.setCheckable(True)
        self._record_btn.clicked.connect(self._on_record_toggled)
        record_layout.addWidget(self._record_btn)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.clicked.connect(self._on_stop_recording)
        self._stop_btn.setEnabled(False)
        record_layout.addWidget(self._stop_btn)

        self._time_label = QLabel("00:00")
        self._time_label.setMinimumWidth(50)
        record_layout.addWidget(self._time_label)

        self._save_wav_btn = QPushButton("Save WAV")
        self._save_wav_btn.clicked.connect(self._on_save_wav)
        self._save_wav_btn.setEnabled(False)
        record_layout.addWidget(self._save_wav_btn)

        self._save_midi_btn = QPushButton("Save MIDI")
        self._save_midi_btn.clicked.connect(self._on_save_midi)
        self._save_midi_btn.setEnabled(False)
        record_layout.addWidget(self._save_midi_btn)

        layout.addWidget(record_group)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)

        self._midi_status = QLabel("MIDI: Not connected")
        status_layout.addWidget(self._midi_status)

        self._audio_status = QLabel("Audio: Ready")
        status_layout.addWidget(self._audio_status)

        self._sustain_status = QLabel("Sustain: Off")
        status_layout.addWidget(self._sustain_status)

        self._notes_status = QLabel("Notes: 0")
        status_layout.addWidget(self._notes_status)

        layout.addWidget(status_group)

        # Add stretch to push everything up
        layout.addStretch()

    def _setup_timer(self):
        """Setup timer for recording time display."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)

    def _on_volume_changed(self, value: int):
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)

    def _on_synth_changed(self, text: str):
        self._soundfont_btn.setEnabled(text == "SoundFont")
        self.synth_changed.emit(text)

    def _on_load_soundfont(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load SoundFont", "", "SoundFont Files (*.sf2)"
        )
        if path:
            self.soundfont_loaded.emit(path)

    def _on_record_toggled(self, checked: bool):
        self._recording = checked
        self._record_btn.setText("● Recording..." if checked else "● Record")
        self._stop_btn.setEnabled(checked)
        if checked:
            self._record_time = 0
            self._timer.start(1000)
        self.record_toggled.emit(checked)

    def _on_stop_recording(self):
        self._record_btn.setChecked(False)
        self._on_record_toggled(False)
        self._timer.stop()
        self._save_wav_btn.setEnabled(True)
        self._save_midi_btn.setEnabled(True)

    def _on_save_wav(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save WAV", "recording.wav", "WAV Files (*.wav)"
        )
        if path:
            self.save_wav.emit(path)

    def _on_save_midi(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MIDI", "recording.mid", "MIDI Files (*.mid)"
        )
        if path:
            self.save_midi.emit(path)

    def _update_time(self):
        self._record_time += 1
        mins = self._record_time // 60
        secs = self._record_time % 60
        self._time_label.setText(f"{mins:02d}:{secs:02d}")

    # Public methods to update status
    def set_midi_status(self, connected: bool, name: str = ""):
        if connected:
            self._midi_status.setText(f"MIDI: {name} ✓")
        else:
            self._midi_status.setText("MIDI: Not connected")

    def set_sustain_status(self, on: bool):
        self._sustain_status.setText(f"Sustain: {'On' if on else 'Off'}")

    def set_notes_count(self, count: int):
        self._notes_status.setText(f"Notes: {count}")
```

**Step 3: Commit**

```bash
git add gui/
git commit -m "feat: add PyQt6 main window"
```

---

## Task 10: Application Integration

**Files:**
- Modify: `main.py`

**Step 1: Integrate all components**

Update `main.py`:

```python
#!/usr/bin/env python3
"""Piano Player - MIDI to audio application."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from gui.main_window import MainWindow
from audio.engine import AudioEngine
from audio.simple_synth import SimpleSynth
from midi.input import MidiInputThread, MidiMessage
from midi.recorder import MidiRecorder
from recording.wav_recorder import WavRecorder


class PianoPlayer(QObject):
    """Main application controller."""

    # Signal to update UI from MIDI thread
    midi_received = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        # Create components
        self._synth = SimpleSynth()
        self._engine = AudioEngine()
        self._engine.set_synth(self._synth)

        self._midi_thread = MidiInputThread()
        self._midi_recorder = MidiRecorder()
        self._wav_recorder = None
        self._wav_path = None

        # Create window
        self._window = MainWindow()

        # Connect signals
        self._connect_signals()

        # Start MIDI input
        self._midi_thread.add_callback(self._on_midi_message)
        self._midi_thread.start()

        # Update MIDI status
        ports = MidiInputThread.list_ports()
        for port in ports:
            if "casio" in port.lower():
                self._window.set_midi_status(True, port)
                break

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self._window.volume_changed.connect(self._on_volume_changed)
        self._window.record_toggled.connect(self._on_record_toggled)
        self._window.save_wav.connect(self._on_save_wav)
        self._window.save_midi.connect(self._on_save_midi)

        # Thread-safe MIDI handling
        self.midi_received.connect(self._handle_midi_in_main_thread)

    def _on_midi_message(self, msg: MidiMessage):
        """Called from MIDI thread - emit signal for main thread."""
        self.midi_received.emit(msg)

    def _handle_midi_in_main_thread(self, msg: MidiMessage):
        """Handle MIDI message in main thread."""
        if msg.type == "note_on":
            self._synth.note_on(msg.note, msg.velocity)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_on(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self._synth.note_off(msg.note)
            if self._midi_recorder.is_recording:
                self._midi_recorder.note_off(msg.note)
        elif msg.type == "sustain":
            if msg.value:
                self._synth.sustain_on()
            else:
                self._synth.sustain_off()
            self._window.set_sustain_status(msg.value)
            if self._midi_recorder.is_recording:
                self._midi_recorder.sustain(msg.value)

        # Update note count
        self._window.set_notes_count(len(self._synth._notes))

    def _on_volume_changed(self, volume: float):
        self._engine.volume = volume

    def _on_record_toggled(self, recording: bool):
        if recording:
            self._midi_recorder.start()
            # Create temp WAV file
            import tempfile
            self._wav_path = tempfile.mktemp(suffix=".wav")
            self._wav_recorder = WavRecorder(self._wav_path)
            self._wav_recorder.start()
            self._engine.set_audio_callback(self._wav_recorder.write)
        else:
            self._midi_recorder.stop()
            if self._wav_recorder:
                self._wav_recorder.stop()
                self._engine.set_audio_callback(None)

    def _on_save_wav(self, path: str):
        if self._wav_path:
            import shutil
            shutil.copy(self._wav_path, path)

    def _on_save_midi(self, path: str):
        self._midi_recorder.save(path)

    def start(self):
        """Start the application."""
        self._engine.start()
        self._window.show()

    def stop(self):
        """Stop the application."""
        self._midi_thread.stop()
        self._engine.stop()


def main():
    app = QApplication(sys.argv)
    player = PianoPlayer()
    player.start()

    result = app.exec()

    player.stop()
    return result


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Verify it runs**

Run: `python main.py`
Expected: Window opens, connects to MIDI, plays sound when keys pressed

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: integrate all components in main application"
```

---

## Task 11: SoundFont Synthesizer (Optional Enhancement)

**Files:**
- Create: `audio/soundfont_synth.py`
- Modify: `main.py`

**Step 1: Create SoundFont synthesizer wrapper**

Create `audio/soundfont_synth.py`:

```python
"""SoundFont synthesizer using FluidSynth."""

import numpy as np
from typing import Optional

try:
    import fluidsynth
    FLUIDSYNTH_AVAILABLE = True
except ImportError:
    FLUIDSYNTH_AVAILABLE = False


class SoundFontSynth:
    """FluidSynth-based synthesizer for realistic piano sound."""

    def __init__(self, sample_rate: int = 44100):
        if not FLUIDSYNTH_AVAILABLE:
            raise ImportError("pyfluidsynth not installed")

        self.sample_rate = sample_rate
        self._fs = fluidsynth.Synth(samplerate=float(sample_rate))
        self._sfid: Optional[int] = None
        self._fs.start(driver="alsa")  # or "pulseaudio", "pipewire"

    def load_soundfont(self, path: str) -> bool:
        """Load a SoundFont file. Returns True on success."""
        try:
            self._sfid = self._fs.sfload(path)
            self._fs.program_select(0, self._sfid, 0, 0)  # Channel 0, bank 0, preset 0
            return True
        except Exception as e:
            print(f"Failed to load SoundFont: {e}")
            return False

    def note_on(self, note: int, velocity: int):
        """Start playing a note."""
        self._fs.noteon(0, note, velocity)

    def note_off(self, note: int):
        """Stop playing a note."""
        self._fs.noteoff(0, note)

    def sustain_on(self):
        """Enable sustain pedal."""
        self._fs.cc(0, 64, 127)

    def sustain_off(self):
        """Disable sustain pedal."""
        self._fs.cc(0, 64, 0)

    def generate(self, num_samples: int) -> np.ndarray:
        """Generate audio samples."""
        # FluidSynth generates stereo, we mix to mono
        samples = self._fs.get_samples(num_samples)
        # Convert to numpy and mix stereo to mono
        arr = np.frombuffer(samples, dtype=np.int16).astype(np.float32) / 32768.0
        left = arr[0::2]
        right = arr[1::2]
        return (left + right) / 2

    def cleanup(self):
        """Clean up resources."""
        if self._sfid is not None:
            self._fs.sfunload(self._sfid)
        self._fs.delete()
```

**Step 2: Update main.py to support synth switching**

Add to PianoPlayer class:

```python
    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self._window.volume_changed.connect(self._on_volume_changed)
        self._window.synth_changed.connect(self._on_synth_changed)
        self._window.soundfont_loaded.connect(self._on_soundfont_loaded)
        # ... rest of connections

    def _on_synth_changed(self, name: str):
        if name == "Simple Synth":
            self._synth = SimpleSynth()
            self._engine.set_synth(self._synth)

    def _on_soundfont_loaded(self, path: str):
        try:
            from audio.soundfont_synth import SoundFontSynth
            sf_synth = SoundFontSynth()
            if sf_synth.load_soundfont(path):
                self._synth = sf_synth
                self._engine.set_synth(self._synth)
        except ImportError:
            print("SoundFont support not available")
```

**Step 3: Commit**

```bash
git add audio/soundfont_synth.py main.py
git commit -m "feat: add SoundFont synthesizer support"
```

---

## Summary Checklist

- [ ] Task 1: Project setup (requirements.txt, main.py, .gitignore)
- [ ] Task 2: AudioEngine foundation
- [ ] Task 3: SimpleSynth with ADSR
- [ ] Task 4: MIDI input handler
- [ ] Task 5: Sustain pedal support
- [ ] Task 6: WAV recorder
- [ ] Task 7: MIDI recorder
- [ ] Task 8: Audio output streaming
- [ ] Task 9: PyQt6 main window
- [ ] Task 10: Application integration
- [ ] Task 11: SoundFont synthesizer (optional)
