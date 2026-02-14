import unittest

from gui.falling_notes_widget import NoteEvent, SustainEvent
from piano_player.services.midi_files import MidiFileService


class MidiFileServiceConversionTests(unittest.TestCase):
    def test_recorder_events_to_notes_respects_offset(self):
        events = [
            {"type": "note_on", "note": 60, "velocity": 100, "time": 0.2},
            {"type": "note_off", "note": 60, "velocity": 0, "time": 0.8},
        ]

        note_events = MidiFileService.recorder_events_to_notes(events, offset=1.5)

        self.assertEqual(len(note_events), 1)
        note = note_events[0]
        self.assertEqual(note.note, 60)
        self.assertEqual(note.velocity, 100)
        self.assertAlmostEqual(note.start_time, 1.7)
        self.assertAlmostEqual(note.duration, 0.6)

    def test_recorder_events_to_sustain_respects_offset(self):
        events = [
            {"type": "sustain", "value": True, "time": 0.1},
            {"type": "sustain", "value": False, "time": 0.9},
        ]

        sustain_events = MidiFileService.recorder_events_to_sustain(events, offset=2.0)

        self.assertEqual(
            sustain_events,
            [
                SustainEvent(time=2.1, on=True),
                SustainEvent(time=2.9, on=False),
            ],
        )

    def test_save_then_load_round_trip(self):
        import tempfile
        from pathlib import Path

        notes = [
            NoteEvent(note=60, start_time=0.0, duration=0.5, velocity=100),
            NoteEvent(note=64, start_time=0.5, duration=0.5, velocity=110),
        ]
        sustain = [
            SustainEvent(time=0.25, on=True),
            SustainEvent(time=1.0, on=False),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            midi_path = Path(tmpdir) / "roundtrip.mid"
            MidiFileService.save(str(midi_path), notes, sustain)
            loaded_notes, loaded_sustain = MidiFileService.load(str(midi_path))

        self.assertEqual(len(loaded_notes), 2)
        self.assertEqual([n.note for n in loaded_notes], [60, 64])
        self.assertEqual(len(loaded_sustain), 2)
        self.assertTrue(loaded_sustain[0].on)
        self.assertFalse(loaded_sustain[1].on)


if __name__ == "__main__":
    unittest.main()
