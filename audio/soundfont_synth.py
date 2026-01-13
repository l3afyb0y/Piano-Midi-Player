"""SoundFont synthesizer using FluidSynth."""

import threading
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
        self._notes: set = set()  # Track active notes for UI
        self._notes_lock = threading.Lock()
        # Not using FluidSynth's own audio driver - we pull samples manually
        # Gain range is 0.0-10.0, default is 0.2 which is very quiet
        self._fs.setting('synth.gain', 2.0)
        # Tune internal buffers for smoother generation
        self._fs.setting('synth.polyphony', 64)  # Limit simultaneous voices
        self._fs.setting('synth.cpu-cores', 2)  # Use multiple cores if available

    def load_soundfont(self, path: str) -> bool:
        """Load a SoundFont file. Returns True on success."""
        try:
            if self._sfid is not None:
                self._fs.sfunload(self._sfid)
            self._sfid = self._fs.sfload(path)
            self._fs.program_select(0, self._sfid, 0, 0)  # Channel 0, bank 0, preset 0 (piano)
            # Set up channel 9 for GM drums (bank 128 = percussion)
            self._fs.program_select(9, self._sfid, 128, 0)
            print(f"Loaded SoundFont: {path}")
            return True
        except Exception as e:
            print(f"Failed to load SoundFont: {e}")
            return False

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
        return ((left + right) / 2).astype(np.float32)

    def cleanup(self):
        """Clean up resources."""
        if self._sfid is not None:
            self._fs.sfunload(self._sfid)
        self._fs.delete()

    def active_notes_count(self) -> int:
        """Return number of currently active notes."""
        with self._notes_lock:
            return len(self._notes)
