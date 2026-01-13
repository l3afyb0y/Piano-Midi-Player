"""Metronome audio generator."""

import numpy as np
from PyQt6.QtCore import QTimer, QObject, pyqtSignal


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

        # Timer for beat timing
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_beat)

        # Generate click sound (short sine wave burst)
        self._click_samples = self._generate_click()

    def _generate_click(self) -> np.ndarray:
        """Generate a short click sound."""
        duration = 0.02  # 20ms click
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples, dtype=np.float32)

        # Higher frequency for accent, with quick decay
        freq = 1000  # Hz
        envelope = np.exp(-t * 50)  # Quick exponential decay
        click = np.sin(2 * np.pi * freq * t) * envelope * 0.5

        return click.astype(np.float32)

    @property
    def bpm(self) -> int:
        return self._bpm

    @bpm.setter
    def bpm(self, value: int):
        self._bpm = max(20, min(300, value))  # Clamp to reasonable range
        if self._running:
            # Restart timer with new interval
            self._timer.setInterval(int(60000 / self._bpm))

    def set_click_callback(self, callback):
        """Set callback to play click sound. Callback receives numpy array."""
        self._click_callback = callback

    def start(self):
        """Start the metronome."""
        if self._running:
            return
        self._running = True
        interval_ms = int(60000 / self._bpm)  # ms per beat
        self._timer.start(interval_ms)
        # Immediately play first beat
        self._on_beat()

    def stop(self):
        """Stop the metronome."""
        self._running = False
        self._timer.stop()

    def is_running(self) -> bool:
        return self._running

    def _on_beat(self):
        """Called on each beat."""
        self.beat.emit()
        if self._click_callback:
            self._click_callback(self._click_samples.copy())

    def get_click_samples(self) -> np.ndarray:
        """Get the click sound samples."""
        return self._click_samples.copy()
