"""Simple additive synthesizer with ADSR envelope."""

import threading
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
        self._sustain = False
        self._sustained_notes: set = set()
        self._lock = threading.Lock()

    def note_on(self, note_number: int, velocity: int):
        """Start playing a note."""
        frequency = 440.0 * (2.0 ** ((note_number - 69) / 12.0))
        with self._lock:
            self._notes[note_number] = Note(
                frequency=frequency,
                velocity=velocity / 127.0,
                phase=0.0,
                envelope=0.0,
                stage="attack",
                released=False,
            )

    def note_off(self, note_number: int):
        """Release a note (or hold if sustain is on)."""
        with self._lock:
            if note_number in self._notes:
                if self._sustain:
                    self._sustained_notes.add(note_number)
                else:
                    self._notes[note_number].released = True
                    self._notes[note_number].stage = "release"

    def sustain_on(self):
        """Enable sustain pedal."""
        with self._lock:
            self._sustain = True

    def sustain_off(self):
        """Disable sustain pedal and release held notes."""
        with self._lock:
            self._sustain = False
            for note_num in self._sustained_notes:
                if note_num in self._notes:
                    self._notes[note_num].released = True
                    self._notes[note_num].stage = "release"
            self._sustained_notes.clear()

    def generate(self, num_samples: int) -> np.ndarray:
        """Generate audio samples."""
        with self._lock:
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

    def active_notes_count(self) -> int:
        """Return number of currently active notes."""
        with self._lock:
            return len(self._notes)

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
