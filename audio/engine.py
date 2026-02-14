"""Audio engine - generates and outputs audio buffers."""

import threading
import queue
import os
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

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 384):
        self.sample_rate = sample_rate
        env_buffer = os.environ.get("PIANO_PLAYER_BUFFER_SIZE", "").strip()
        if env_buffer:
            try:
                buffer_size = max(128, int(env_buffer))
            except ValueError:
                pass
        self.buffer_size = buffer_size  # 384 @ 44.1kHz ~= 8.7ms, more underrun-resistant than 256
        self._latency_hint = self._parse_latency_hint(os.environ.get("PIANO_PLAYER_AUDIO_LATENCY", ""))
        self._volume = 0.8
        self._synth: Optional[Synthesizer] = None
        self._stream: Optional[sd.OutputStream] = None
        self._running = False
        self._output_device: Optional[int] = None
        self._synth_lock = threading.Lock()  # Only for synth swapping, not generation
        self._audio_callback_fn: Optional[Callable[[np.ndarray], None]] = None
        self._mix_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._mix_current: Optional[np.ndarray] = None
        self._mix_index = 0

    @property
    def volume(self) -> float:
        return self._volume

    @staticmethod
    def _parse_latency_hint(raw: str):
        value = (raw or "").strip().lower()
        if not value:
            return None
        if value in ("low", "high"):
            return value
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @volume.setter
    def volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))

    def set_synth(self, synth: Synthesizer):
        """Set the synthesizer to use."""
        with self._synth_lock:
            self._synth = synth

    @property
    def output_device(self) -> Optional[int]:
        return self._output_device

    @staticmethod
    def list_output_devices() -> list[tuple[int, str]]:
        """Return available output devices as (index, name)."""
        devices = sd.query_devices()
        outputs: list[tuple[int, str]] = []
        for idx, dev in enumerate(devices):
            if dev.get("max_output_channels", 0) > 0:
                outputs.append((idx, dev.get("name", f"Device {idx}")))
        return outputs

    @staticmethod
    def default_output_device() -> Optional[int]:
        default_dev = sd.default.device
        if isinstance(default_dev, (list, tuple)) and len(default_dev) > 1:
            output_idx = default_dev[1]
            if isinstance(output_idx, int) and output_idx >= 0:
                return output_idx
        return None

    def set_output_device(self, device_index: Optional[int]) -> bool:
        """Set active output device. Restarts stream if already running."""
        if device_index is not None and device_index < 0:
            device_index = None
        if self._output_device == device_index:
            return True

        previous = self._output_device
        was_running = self._running
        if was_running:
            self.stop()

        self._output_device = device_index
        if not was_running:
            return True

        try:
            self.start()
            return True
        except Exception as exc:
            print(f"Failed to set audio output device: {exc}")
            self._output_device = previous
            if previous != device_index:
                try:
                    self.start()
                except Exception as restart_exc:
                    print(f"Failed to restart previous audio output: {restart_exc}")
            return False

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

        outdata[:, 0] = np.clip(buffer, -1.0, 1.0)

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
            device=self._output_device,
            latency=self._latency_hint,
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
