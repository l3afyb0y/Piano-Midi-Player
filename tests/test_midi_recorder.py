import unittest
from unittest.mock import patch

from midi.recorder import MidiRecorder


class MidiRecorderStopTests(unittest.TestCase):
    def test_stop_flushes_active_notes(self):
        recorder = MidiRecorder()
        with patch("time.time") as mock_time:
            mock_time.return_value = 10.0
            recorder.start()
            mock_time.return_value = 10.1
            recorder.note_on(60, 90)
            mock_time.return_value = 10.5
            recorder.stop()

        events = recorder.get_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "note_on")
        self.assertAlmostEqual(events[0]["time"], 0.1)
        self.assertEqual(events[1]["type"], "note_off")
        self.assertAlmostEqual(events[1]["time"], 0.5)
        self.assertFalse(recorder.is_recording)

    def test_stop_records_sustain_release(self):
        recorder = MidiRecorder()
        with patch("time.time") as mock_time:
            mock_time.return_value = 5.0
            recorder.start()
            mock_time.return_value = 5.2
            recorder.sustain(True)
            mock_time.return_value = 6.0
            recorder.stop()

        events = recorder.get_events()
        self.assertEqual(events[0]["type"], "sustain")
        self.assertTrue(events[0]["value"])
        self.assertEqual(events[-1]["type"], "sustain")
        self.assertFalse(events[-1]["value"])
        self.assertAlmostEqual(events[-1]["time"], 1.0)

    def test_stop_emits_missing_note_offs_for_duplicate_notes(self):
        recorder = MidiRecorder()
        with patch("time.time") as mock_time:
            mock_time.return_value = 1.0
            recorder.start()
            mock_time.return_value = 1.1
            recorder.note_on(60, 100)
            recorder.note_on(60, 110)
            mock_time.return_value = 1.4
            recorder.note_off(60)
            mock_time.return_value = 1.6
            recorder.stop()

        off_events = [event for event in recorder.get_events() if event["type"] == "note_off"]
        self.assertEqual(len(off_events), 2)
        self.assertAlmostEqual(off_events[-1]["time"], 0.6)


if __name__ == "__main__":
    unittest.main()
