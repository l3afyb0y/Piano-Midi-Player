"""WAV file recording."""

import queue
import threading
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
        self._write_queue: queue.SimpleQueue[np.ndarray | None] = queue.SimpleQueue()
        self._writer_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start recording."""
        if self._running:
            return
        self._write_queue = queue.SimpleQueue()
        self._wav_file = wave.open(self._path, 'wb')
        self._wav_file.setnchannels(self._channels)
        self._wav_file.setsampwidth(2)  # 16-bit
        self._wav_file.setframerate(self._sample_rate)
        self._frames_written = 0
        self._running = True
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def _writer_loop(self):
        while True:
            chunk = self._write_queue.get()
            if chunk is None:
                break
            if self._wav_file is None:
                continue
            int_samples = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype(np.int16, copy=False)
            self._wav_file.writeframes(int_samples.tobytes())
            self._frames_written += len(chunk)
        self._running = False

    def write(self, samples: np.ndarray):
        """Queue audio samples for asynchronous WAV writing."""
        if self._wav_file is None or not self._running:
            return
        chunk = np.asarray(samples, dtype=np.float32)
        if chunk.ndim != 1:
            chunk = chunk.reshape(-1)
        self._write_queue.put(chunk.copy())

    def stop(self):
        """Stop recording and close file."""
        if not self._running and self._wav_file is None:
            return
        self._write_queue.put(None)
        if self._writer_thread:
            self._writer_thread.join(timeout=2.0)
            self._writer_thread = None
        self._running = False
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
        return self._running
