import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from recording.wav_recorder import WavRecorder


class WavRecorderTests(unittest.TestCase):
    def test_stop_flushes_queued_audio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.wav"
            recorder = WavRecorder(str(target), sample_rate=8000)
            recorder.start()
            recorder.write(np.full(800, 0.1, dtype=np.float32))
            recorder.stop()

            with wave.open(str(target), "rb") as handle:
                self.assertEqual(handle.getnframes(), 800)
                self.assertEqual(handle.getframerate(), 8000)

    def test_start_and_stop_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.wav"
            recorder = WavRecorder(str(target), sample_rate=8000)
            recorder.start()
            recorder.start()  # no-op while running
            recorder.write(np.full(256, 0.2, dtype=np.float32))
            recorder.stop()
            recorder.stop()  # no-op after already stopped

            with wave.open(str(target), "rb") as handle:
                self.assertGreaterEqual(handle.getnframes(), 256)


if __name__ == "__main__":
    unittest.main()

