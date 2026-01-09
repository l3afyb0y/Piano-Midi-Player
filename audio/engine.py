"""Audio engine - generates and outputs audio buffers."""

import threading
import numpy as np
from typing import Optional, Protocol, Callable
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
        self._audio_callback_fn: Optional[Callable[[np.ndarray], None]] = None

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

    def set_audio_callback(self, callback: Optional[Callable[[np.ndarray], None]]):
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
