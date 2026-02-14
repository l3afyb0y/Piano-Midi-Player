import unittest

import numpy as np

from audio.simple_synth import SimpleSynth


class SimpleSynthTests(unittest.TestCase):
    def test_sustained_note_decays_while_pedal_held(self):
        synth = SimpleSynth(sample_rate=44100, instrument="Piano")
        synth.sustain_on()
        synth.note_on(60, 100)

        # Let the note reach a stable envelope level before release.
        for _ in range(25):
            synth.generate(256)

        synth.note_off(60)
        self.assertGreater(synth.active_notes_count(), 0)

        max_blocks = int(((synth._pedal_release + 1.0) * synth.sample_rate) // 256) + 2
        for _ in range(max_blocks):
            synth.generate(256)
            if synth.active_notes_count() == 0:
                break

        self.assertEqual(synth.active_notes_count(), 0)

    def test_instrument_profiles_produce_distinct_timbres(self):
        piano = SimpleSynth(sample_rate=44100, instrument="Piano")
        guitar = SimpleSynth(sample_rate=44100, instrument="Guitar")
        piano.note_on(64, 100)
        guitar.note_on(64, 100)

        # Skip initial transient so we compare stable timbre, not just attack shape.
        for _ in range(8):
            piano_buf = piano.generate(256)
            guitar_buf = guitar.generate(256)

        diff = float(np.max(np.abs(piano_buf - guitar_buf)))
        self.assertGreater(diff, 0.01)

    def test_guitar_and_piano_share_pitch_center(self):
        sample_rate = 44100
        note = 60  # Middle C
        expected_hz = 261.625565

        def dominant_hz(inst: str) -> float:
            synth = SimpleSynth(sample_rate=sample_rate, instrument=inst)
            synth.note_on(note, 110)
            for _ in range(12):
                synth.generate(256)
            buf = np.concatenate([synth.generate(256) for _ in range(32)])
            window = np.hanning(len(buf))
            spectrum = np.fft.rfft(buf * window)
            freqs = np.fft.rfftfreq(len(buf), d=1.0 / sample_rate)
            idx = int(np.argmax(np.abs(spectrum[1:])) + 1)
            return float(freqs[idx])

        piano_hz = dominant_hz("Piano")
        guitar_hz = dominant_hz("Guitar")

        self.assertLess(abs(piano_hz - expected_hz), 8.0)
        self.assertLess(abs(guitar_hz - expected_hz), 8.0)
        self.assertLess(abs(piano_hz - guitar_hz), 3.0)


if __name__ == "__main__":
    unittest.main()
