"""Metronome audio generator."""

import numpy as np
import time
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt


class Metronome(QObject):
    """Generates metronome click at specified BPM."""

    # Signal emitted on each beat (for visual feedback)
    beat = pyqtSignal()

    def __init__(self, sample_rate: int = 44100):
        super().__init__()
        self.sample_rate = sample_rate
        self._bpm = 120
        self._running = False
        self._click_callback = None
        self._beat_interval = 60.0 / self._bpm
        self._next_beat_at: float | None = None
        self._beats_per_cycle = 4
        self._accent_beat = 4
        self._beat_index = 0

        # Timer for beat timing
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_beat)

        # Generate click sounds.
        self._click_samples = self._generate_click(accent=False)
        self._accent_click_samples = self._generate_click(accent=True)

    def _generate_click(self, accent: bool) -> np.ndarray:
        """Generate a short click sound."""
        duration = 0.03 if accent else 0.018
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples, dtype=np.float32)

        freq = 1700 if accent else 900  # Hz
        envelope = np.exp(-t * 50)  # Quick exponential decay
        amplitude = 0.78 if accent else 0.30
        click = np.sin(2 * np.pi * freq * t) * envelope * amplitude

        return click.astype(np.float32)

    @property
    def bpm(self) -> int:
        return self._bpm

    @bpm.setter
    def bpm(self, value: int):
        self._bpm = max(20, min(300, value))  # Clamp to reasonable range
        self._beat_interval = 60.0 / self._bpm
        if self._running:
            now = time.perf_counter()
            self._next_beat_at = now + self._beat_interval
            self._schedule_next_beat(now)

    def set_click_callback(self, callback):
        """Set callback to play click sound. Callback receives numpy array."""
        self._click_callback = callback

    def set_meter(self, beats_per_cycle: int, accent_beat: int | None = None):
        self._beats_per_cycle = max(1, beats_per_cycle)
        if accent_beat is None:
            accent_beat = self._beats_per_cycle
        self._accent_beat = min(self._beats_per_cycle, max(1, accent_beat))

    def reset_counter(self):
        self._beat_index = 0

    def start(self):
        """Start the metronome."""
        if self._running:
            return
        self._running = True
        self._beat_index = 0
        self._next_beat_at = time.perf_counter()
        # Immediately play first beat
        self._on_beat()

    def stop(self):
        """Stop the metronome."""
        self._running = False
        self._next_beat_at = None
        self._timer.stop()

    def is_running(self) -> bool:
        return self._running

    def _on_beat(self):
        """Called on each beat."""
        if not self._running:
            return

        self.beat.emit()
        if self._click_callback:
            self._beat_index = (self._beat_index % self._beats_per_cycle) + 1
            is_accent = self._beat_index == self._accent_beat
            samples = self._accent_click_samples if is_accent else self._click_samples
            self._click_callback(samples.copy())

        now = time.perf_counter()
        if self._next_beat_at is None:
            self._next_beat_at = now
        self._next_beat_at += self._beat_interval
        while self._next_beat_at <= now:
            self._next_beat_at += self._beat_interval
        self._schedule_next_beat(now)

    def _schedule_next_beat(self, now: float):
        if not self._running or self._next_beat_at is None:
            return
        delay_ms = max(1, int(round((self._next_beat_at - now) * 1000)))
        self._timer.start(delay_ms)

    def get_click_samples(self) -> np.ndarray:
        """Get the click sound samples."""
        return self._click_samples.copy()
