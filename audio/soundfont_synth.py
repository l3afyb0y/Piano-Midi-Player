"""SoundFont synthesizer using FluidSynth."""

import contextlib
import os
import threading
import numpy as np
from typing import Optional

_FLUIDSYNTH_MODULE = None


@contextlib.contextmanager
def _suppress_stderr_fd():
    """Suppress noisy native stderr output for known non-fatal backend warnings."""
    stderr_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(stderr_fd, 2)
        os.close(stderr_fd)
        os.close(devnull_fd)


def _load_fluidsynth():
    global _FLUIDSYNTH_MODULE
    if _FLUIDSYNTH_MODULE is not None:
        return _FLUIDSYNTH_MODULE

    try:
        with _suppress_stderr_fd():
            import fluidsynth as _fluidsynth
    except ImportError:
        return None

    _FLUIDSYNTH_MODULE = _fluidsynth
    return _FLUIDSYNTH_MODULE


class SoundFontSynth:
    """FluidSynth-based synthesizer for realistic piano sound."""

    INSTRUMENT_PRESETS = {
        "Piano": (0, 0),   # Acoustic Grand Piano
        "Guitar": (0, 27),  # Clean Electric Guitar
    }
    INSTRUMENT_PRESET_FALLBACKS = {
        "Piano": [(0, 0), (0, 1), (0, 2)],
        "Guitar": [(0, 27), (0, 26), (0, 24), (0, 25), (0, 0)],
    }
    INSTRUMENT_MIX = {
        "Piano": {"cc7": 112, "cc11": 110, "cc74": 64},
        "Guitar": {"cc7": 88, "cc11": 96, "cc74": 54},
    }

    def __init__(self, sample_rate: int = 44100):
        fluidsynth = _load_fluidsynth()
        if fluidsynth is None:
            raise ImportError("pyfluidsynth not installed")

        self.sample_rate = sample_rate
        self._fluidsynth = fluidsynth
        # We render samples manually via get_samples(), not via FluidSynth's audio driver.
        # Some distro builds emit SDL driver warnings at init time even when unused.
        with _suppress_stderr_fd():
            self._fs = fluidsynth.Synth(samplerate=float(sample_rate))
        self._sfid: Optional[int] = None
        self._instrument = "Piano"
        self._notes: set = set()  # Track active notes for UI
        self._notes_lock = threading.Lock()
        self._output_gain = 1.0
        # Not using FluidSynth's own audio driver - we pull samples manually
        # Keep FluidSynth global gain conservative to avoid preset-dependent clipping.
        self._fs.setting('synth.gain', 0.65)
        # Tune internal buffers for smoother generation
        self._fs.setting('synth.polyphony', 96)  # Keep headroom for sustain-heavy play
        self._fs.setting('synth.cpu-cores', 2)  # Use multiple cores if available

    def load_soundfont(self, path: str) -> bool:
        """Load a SoundFont file. Returns True on success."""
        try:
            if self._sfid is not None:
                self._fs.sfunload(self._sfid)
            self._sfid = self._fs.sfload(path)
            self.set_instrument(self._instrument)
            # Set up channel 9 for GM drums (bank 128 = percussion)
            self._fs.program_select(9, self._sfid, 128, 0)
            print(f"Loaded SoundFont: {path}")
            return True
        except Exception as e:
            print(f"Failed to load SoundFont: {e}")
            return False

    def set_instrument(self, instrument: str):
        self._instrument = instrument if instrument in self.INSTRUMENT_PRESETS else "Piano"
        if self._sfid is None:
            return
        candidates = self.INSTRUMENT_PRESET_FALLBACKS.get(
            self._instrument,
            [self.INSTRUMENT_PRESETS[self._instrument]],
        )
        for bank, preset in candidates:
            try:
                status = self._fs.program_select(0, self._sfid, bank, preset)
            except Exception:
                continue
            # pyfluidsynth variants may return 0 or None on success.
            if status in (0, None):
                break
        else:
            # Last-resort attempt with the primary preset.
            primary_bank, primary_preset = self.INSTRUMENT_PRESETS[self._instrument]
            self._fs.program_select(0, self._sfid, primary_bank, primary_preset)

        mix = self.INSTRUMENT_MIX[self._instrument]
        self._fs.cc(0, 7, int(mix["cc7"]))     # channel volume
        self._fs.cc(0, 11, int(mix["cc11"]))   # expression
        self._fs.cc(0, 74, int(mix["cc74"]))   # brightness/tone

    def note_on(self, note: int, velocity: int):
        """Start playing a note."""
        self._fs.noteon(0, note, velocity)
        with self._notes_lock:
            self._notes.add(note)

    def note_off(self, note: int):
        """Stop playing a note."""
        self._fs.noteoff(0, note)
        with self._notes_lock:
            self._notes.discard(note)

    def sustain_on(self):
        """Enable sustain pedal."""
        self._fs.cc(0, 64, 127)

    def sustain_off(self):
        """Disable sustain pedal."""
        self._fs.cc(0, 64, 0)

    def generate(self, num_samples: int) -> np.ndarray:
        """Generate audio samples."""
        # FluidSynth generates interleaved stereo int16
        samples = self._fs.get_samples(num_samples)
        # Convert to numpy float32 and mix stereo to mono
        arr = np.frombuffer(samples, dtype=np.int16).astype(np.float32) / 32768.0
        # Interleaved stereo: [L0, R0, L1, R1, ...]
        left = arr[0::2]
        right = arr[1::2]
        mono = ((left + right) / 2).astype(np.float32)

        # Lightweight output gain smoothing to prevent crunchy clipping on bright presets.
        peak = float(np.max(np.abs(mono)))
        if peak > 1e-9:
            target = min(1.0, 0.94 / peak)
            if target < self._output_gain:
                self._output_gain += (target - self._output_gain) * 0.35
            else:
                self._output_gain += (target - self._output_gain) * 0.06
            mono *= self._output_gain

        return mono

    def cleanup(self):
        """Clean up resources."""
        if self._sfid is not None:
            self._fs.sfunload(self._sfid)
        self._fs.delete()

    def active_notes_count(self) -> int:
        """Return number of currently active notes."""
        with self._notes_lock:
            return len(self._notes)
