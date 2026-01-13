"""Audio engine - generates and outputs audio buffers."""

import threading
import queue
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

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size  # 256 @ 44.1kHz = ~6ms per buffer
        self._volume = 0.8
        self._synth: Optional[Synthesizer] = None
        self._stream: Optional[sd.OutputStream] = None
        self._running = False
        self._synth_lock = threading.Lock()  # Only for synth swapping, not generation
        self._audio_callback_fn: Optional[Callable[[np.ndarray], None]] = None
        self._mix_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._mix_current: Optional[np.ndarray] = None
        self._mix_index = 0

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))

    def set_synth(self, synth: Synthesizer):
        """Set the synthesizer to use."""
        with self._synth_lock:
            self._synth = synth

    def set_audio_callback(self, callback: Optional[Callable[[np.ndarray], None]]):
        """Set callback to receive generated audio (for recording)."""
        self._audio_callback_fn = callback

    def queue_audio(self, samples: np.ndarray):
        """Queue one-shot audio to mix into output (e.g., metronome click)."""
        if samples is None or len(samples) == 0:
            return
        self._mix_queue.put(np.asarray(samples, dtype=np.float32).copy())

    def _audio_callback(self, outdata, frames, _time_info, _status):
        """Sounddevice callback - runs in audio thread.

        IMPORTANT: Avoid blocking here - real-time thread cannot wait.
        Synth reference is stable; only swapped via set_synth().
        """
        synth = self._synth  # Atomic read
        if synth:
            buffer = synth.generate(frames)
            buffer = buffer * self._volume
        else:
            buffer = np.zeros(frames, dtype=np.float32)

        # Mix any queued one-shot audio (e.g., metronome click).
        if self._mix_current is None:
            try:
                self._mix_current = self._mix_queue.get_nowait()
                self._mix_index = 0
            except queue.Empty:
                self._mix_current = None

        if self._mix_current is not None:
            remaining = len(self._mix_current) - self._mix_index
            if remaining <= 0:
                self._mix_current = None
            else:
                count = min(frames, remaining)
                buffer[:count] += (
                    self._mix_current[self._mix_index:self._mix_index + count] * self._volume
                )
                self._mix_index += count
                if self._mix_index >= len(self._mix_current):
                    self._mix_current = None

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
            latency='low',  # Low latency for responsive playing
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
        synth = self._synth
        if synth:
            return synth.generate(self.buffer_size) * self._volume
        return np.zeros(self.buffer_size, dtype=np.float32)
