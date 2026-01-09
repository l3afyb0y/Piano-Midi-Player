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
