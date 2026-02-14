"""Simple additive synthesizer with switchable instrument profiles."""

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
    stage: str = "attack"  # attack, decay, sustain, pedal, release, off
    released: bool = False


class SimpleSynth:
    """Additive synthesizer with instrument presets and sustain handling."""

    INSTRUMENTS = {
        "Piano": {
            "attack": 0.010,
            "decay": 0.120,
            "sustain_level": 0.42,
            "release": 0.34,
            "pedal_release": 2.30,
            "gain": 0.17,
            "harmonics": [
                (1.0, 1.00),
                (2.0, 0.36),
                (3.0, 0.14),
                (4.0, 0.06),
            ],
            "poly_comp": 0.09,
            "low_balance_hz": 150.0,
            "low_min_gain": 0.72,
            "hp_hz": 28.0,
            "lp_hz": 7600.0,
        },
        "Guitar": {
            "attack": 0.004,
            "decay": 0.150,
            "sustain_level": 0.12,
            "release": 0.22,
            "pedal_release": 0.95,
            "gain": 0.16,
            "harmonics": [
                (1.0, 1.00),
                (2.0, 0.26),
                (3.0, 0.12),
                (4.0, 0.05),
            ],
            "poly_comp": 0.12,
            "low_balance_hz": 170.0,
            "low_min_gain": 0.64,
            "hp_hz": 40.0,
            "lp_hz": 5600.0,
        },
    }

    DEFAULT_INSTRUMENT = "Piano"
    LIMITER_TARGET_PEAK = 0.92
    LIMITER_ATTACK = 0.30
    LIMITER_RELEASE = 0.08
    POLYPHONY_COMPENSATION = 0.10
    MIX_GAIN_ATTACK = 0.26
    MIX_GAIN_RELEASE = 0.06
    MAX_VOICES = 88

    def __init__(self, sample_rate: int = 44100, instrument: str = DEFAULT_INSTRUMENT):
        self.sample_rate = sample_rate
        self._notes: Dict[int, Note] = {}
        self._sustain = False
        self._sustained_notes: set = set()
        self._lock = threading.Lock()
        self._limiter_gain = 1.0
        self._mix_gain = 1.0
        self._instrument = self.DEFAULT_INSTRUMENT
        self._attack = 0.01
        self._decay = 0.1
        self._sustain_level = 0.4
        self._release = 0.3
        self._pedal_release = 2.0
        self._gain = 0.26
        self._harmonics = [(1.0, 1.0)]
        self._poly_comp = self.POLYPHONY_COMPENSATION
        self._low_balance_hz = 180.0
        self._low_min_gain = 0.6
        self._hp_hz = 30.0
        self._lp_hz = 7000.0
        self._hp_alpha = 0.0
        self._lp_alpha = 0.0
        self._hp_prev_x = 0.0
        self._hp_prev_y = 0.0
        self._lp_prev_y = 0.0
        self._rng = np.random.default_rng()
        self.set_instrument(instrument)

    def set_instrument(self, instrument: str):
        profile = self.INSTRUMENTS.get(instrument, self.INSTRUMENTS[self.DEFAULT_INSTRUMENT])
        self._instrument = instrument if instrument in self.INSTRUMENTS else self.DEFAULT_INSTRUMENT
        self._attack = float(profile["attack"])
        self._decay = float(profile["decay"])
        self._sustain_level = float(profile["sustain_level"])
        self._release = float(profile["release"])
        self._pedal_release = float(profile["pedal_release"])
        self._gain = float(profile["gain"])
        self._harmonics = list(profile["harmonics"])
        self._poly_comp = float(profile.get("poly_comp", self.POLYPHONY_COMPENSATION))
        self._low_balance_hz = float(profile.get("low_balance_hz", 180.0))
        self._low_min_gain = float(profile.get("low_min_gain", 0.6))
        self._hp_hz = float(profile.get("hp_hz", 30.0))
        self._lp_hz = float(profile.get("lp_hz", 7000.0))
        self._recompute_filter_coeffs()
        self._hp_prev_x = 0.0
        self._hp_prev_y = 0.0
        self._lp_prev_y = 0.0

    @property
    def instrument(self) -> str:
        return self._instrument

    def _recompute_filter_coeffs(self):
        dt = 1.0 / self.sample_rate
        hp_rc = 1.0 / (2.0 * np.pi * max(1.0, self._hp_hz))
        lp_rc = 1.0 / (2.0 * np.pi * max(1.0, self._lp_hz))
        self._hp_alpha = hp_rc / (hp_rc + dt)
        self._lp_alpha = dt / (lp_rc + dt)

    def note_on(self, note_number: int, velocity: int):
        """Start playing a note."""
        frequency = 440.0 * (2.0 ** ((note_number - 69) / 12.0))
        random_phase = float(self._rng.random()) / frequency
        with self._lock:
            if len(self._notes) >= self.MAX_VOICES:
                self._steal_voice()
            self._notes[note_number] = Note(
                frequency=frequency,
                velocity=velocity / 127.0,
                phase=random_phase,
                envelope=0.0,
                stage="attack",
                released=False,
            )

    def note_off(self, note_number: int):
        """Release a note (or hold if sustain is on)."""
        with self._lock:
            if note_number in self._notes:
                note = self._notes[note_number]
                note.released = True
                if self._sustain:
                    self._sustained_notes.add(note_number)
                    note.stage = "pedal"
                else:
                    note.stage = "release"

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

            active_count = len(self._notes)
            if active_count > 1:
                # Real acoustic instruments do not sum linearly forever in perceived loudness.
                # Apply light polyphony compensation before limiting.
                target_mix = 1.0 / (1.0 + self._poly_comp * (active_count - 1))
            else:
                target_mix = 1.0
            self._mix_gain = self._smooth_gain(
                current=self._mix_gain,
                target=target_mix,
                attack=self.MIX_GAIN_ATTACK,
                release=self.MIX_GAIN_RELEASE,
            )
            buffer *= self._mix_gain

            buffer = self._apply_limiter(buffer)
            buffer = self._apply_output_filter(buffer)
            return buffer

    def _steal_voice(self):
        if not self._notes:
            return
        victim_key, victim_note = min(
            self._notes.items(),
            key=lambda kv: kv[1].envelope * kv[1].velocity,
        )
        # Avoid abrupt removals that can click/crackle.
        victim_note.released = True
        victim_note.stage = "release"
        victim_note.envelope = min(victim_note.envelope, 0.05)
        self._sustained_notes.discard(victim_key)

    @staticmethod
    def _smooth_gain(current: float, target: float, attack: float, release: float) -> float:
        """Smooth gain changes to avoid zipper/click artifacts."""
        if target < current:
            coeff = attack
        else:
            coeff = release
        coeff = max(0.0, min(1.0, coeff))
        return current + (target - current) * coeff

    def active_notes_count(self) -> int:
        """Return number of currently active notes."""
        with self._lock:
            return len(self._notes)

    def _generate_note(self, note: Note, num_samples: int) -> np.ndarray:
        """Generate samples for a single note with vectorized oscillators."""
        envelope = self._build_envelope_block(note, num_samples)
        if note.stage == "off" and not np.any(envelope):
            return np.zeros(num_samples, dtype=np.float32)

        t = note.phase + (np.arange(num_samples, dtype=np.float32) / self.sample_rate)
        waveform = np.zeros(num_samples, dtype=np.float32)
        # Darken lower notes to avoid buzzy bass buildup under sustain.
        brightness = float(np.clip(note.frequency / 1000.0, 0.30, 1.0))
        low_weight = float(np.clip(note.frequency / self._low_balance_hz, self._low_min_gain, 1.0))
        for harmonic_mult, harmonic_amp in self._harmonics:
            freq = note.frequency * harmonic_mult
            harmonic_tilt = brightness ** max(0.0, harmonic_mult - 1.0)
            waveform += (harmonic_amp * harmonic_tilt) * np.sin(2.0 * np.pi * freq * t)

        note.phase += num_samples / self.sample_rate
        return (waveform * envelope * note.velocity * self._gain * low_weight).astype(np.float32)

    def _apply_limiter(self, buffer: np.ndarray) -> np.ndarray:
        """Apply a lightweight peak limiter to avoid sustain-pedal overload artifacts."""
        peak = float(np.max(np.abs(buffer)))
        if peak <= 1e-9:
            self._limiter_gain = min(1.0, self._limiter_gain + self.LIMITER_RELEASE)
            return buffer

        needed_gain = min(1.0, self.LIMITER_TARGET_PEAK / peak)
        self._limiter_gain = self._smooth_gain(
            current=self._limiter_gain,
            target=needed_gain,
            attack=self.LIMITER_ATTACK,
            release=self.LIMITER_RELEASE,
        )

        return buffer * self._limiter_gain

    def _apply_output_filter(self, buffer: np.ndarray) -> np.ndarray:
        """Apply gentle high-pass/low-pass filtering to reduce rumble and harshness."""
        out = np.empty_like(buffer)
        hp_alpha = self._hp_alpha
        lp_alpha = self._lp_alpha
        prev_x = self._hp_prev_x
        prev_hp = self._hp_prev_y
        prev_lp = self._lp_prev_y

        for i, x in enumerate(buffer):
            hp = hp_alpha * (prev_hp + float(x) - prev_x)
            lp = prev_lp + lp_alpha * (hp - prev_lp)
            out[i] = lp
            prev_x = float(x)
            prev_hp = hp
            prev_lp = lp

        self._hp_prev_x = prev_x
        self._hp_prev_y = prev_hp
        self._lp_prev_y = prev_lp
        return out

    def _build_envelope_block(self, note: Note, num_samples: int) -> np.ndarray:
        """Generate ADSR envelope values for this buffer and update note state."""
        envelope = np.zeros(num_samples, dtype=np.float32)
        dt = 1.0 / self.sample_rate
        i = 0

        while i < num_samples:
            if note.stage == "attack":
                if self._attack <= 0:
                    note.envelope = 1.0
                    note.stage = "decay"
                    continue
                step = dt / self._attack
                remaining = max(1, int(np.ceil((1.0 - note.envelope) / step)))
                block = min(num_samples - i, remaining)
                vals = note.envelope + step * np.arange(1, block + 1, dtype=np.float32)
                vals = np.minimum(vals, 1.0)
                envelope[i:i + block] = vals
                note.envelope = float(vals[-1])
                i += block
                if note.envelope >= 1.0:
                    note.envelope = 1.0
                    note.stage = "decay"
                continue

            if note.stage == "decay":
                if self._decay <= 0:
                    note.envelope = self._sustain_level
                    note.stage = "sustain"
                    continue
                step = dt * (1.0 - self._sustain_level) / self._decay
                remaining = max(1, int(np.ceil((note.envelope - self._sustain_level) / step)))
                block = min(num_samples - i, remaining)
                vals = note.envelope - step * np.arange(1, block + 1, dtype=np.float32)
                vals = np.maximum(vals, self._sustain_level)
                envelope[i:i + block] = vals
                note.envelope = float(vals[-1])
                i += block
                if note.envelope <= self._sustain_level:
                    note.envelope = self._sustain_level
                    note.stage = "sustain"
                continue

            if note.stage == "sustain":
                if note.released:
                    note.stage = "pedal" if self._sustain else "release"
                    continue
                envelope[i:] = note.envelope
                i = num_samples
                continue

            if note.stage == "pedal":
                if self._pedal_release <= 0:
                    note.envelope = 0.0
                    note.stage = "off"
                    continue
                step = dt / self._pedal_release
                remaining = max(1, int(np.ceil(note.envelope / step)))
                block = min(num_samples - i, remaining)
                vals = note.envelope - step * np.arange(1, block + 1, dtype=np.float32)
                vals = np.maximum(vals, 0.0)
                envelope[i:i + block] = vals
                note.envelope = float(vals[-1])
                i += block
                if note.envelope <= 0.0:
                    note.envelope = 0.0
                    note.stage = "off"
                continue

            if note.stage == "release":
                if self._release <= 0:
                    note.envelope = 0.0
                    note.stage = "off"
                    continue
                step = dt / self._release
                remaining = max(1, int(np.ceil(note.envelope / step)))
                block = min(num_samples - i, remaining)
                vals = note.envelope - step * np.arange(1, block + 1, dtype=np.float32)
                vals = np.maximum(vals, 0.0)
                envelope[i:i + block] = vals
                note.envelope = float(vals[-1])
                i += block
                if note.envelope <= 0.0:
                    note.envelope = 0.0
                    note.stage = "off"
                continue

            envelope[i:] = 0.0
            i = num_samples

        return envelope
