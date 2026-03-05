import unittest

from piano_player.synth_modes import SYNTH_SF2, SYNTH_SFZ, normalize_synth_mode


class SynthModesTests(unittest.TestCase):
    def test_legacy_soundfont_alias_maps_to_sfz(self):
        self.assertEqual(normalize_synth_mode("SoundFont"), SYNTH_SFZ)

    def test_unknown_mode_defaults_to_sfz(self):
        self.assertEqual(normalize_synth_mode("unknown-mode"), SYNTH_SFZ)

    def test_known_modes_preserved(self):
        self.assertEqual(normalize_synth_mode(SYNTH_SFZ), SYNTH_SFZ)
        self.assertEqual(normalize_synth_mode(SYNTH_SF2), SYNTH_SF2)


if __name__ == "__main__":
    unittest.main()
