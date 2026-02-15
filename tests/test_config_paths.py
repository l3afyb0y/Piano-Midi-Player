import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import piano_player.config as config


def _write_fake_sf2(path: Path):
    # Minimal SF2-like RIFF header: RIFF <size> sfbk
    path.write_bytes(b"RIFF\x04\x00\x00\x00sfbkDATA")


class ConfigPathResolutionTests(unittest.TestCase):
    def test_saved_path_is_used(self):
        path = config.resolve_midi_directory("~/custom-midi")
        self.assertEqual(path, Path("~/custom-midi").expanduser())

    def test_legacy_dir_with_midi_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy = Path(tmpdir) / "legacy"
            legacy.mkdir()
            (legacy / "song.mid").write_bytes(b"x")

            with patch.object(config, "LEGACY_MIDI_DIR", legacy):
                result = config.resolve_midi_directory("")

            self.assertEqual(result, legacy)

    def test_instrument_specific_env_override_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            piano_sf = Path(tmpdir) / "piano.sf2"
            common_sf = Path(tmpdir) / "common.sf2"
            _write_fake_sf2(piano_sf)
            _write_fake_sf2(common_sf)

            overrides = {"Piano": [str(piano_sf)], "Guitar": []}
            with patch.object(config, "INSTRUMENT_ENV_OVERRIDES", overrides), patch.object(
                config, "COMMON_SOUNDFONT_LOCATIONS", [str(common_sf)]
            ):
                result = config.find_default_soundfont("Piano")

            self.assertEqual(result, str(piano_sf))

    def test_instrument_hint_is_used_when_no_globals_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sf_dir = Path(tmpdir)
            guitar_sf = sf_dir / "warm_guitar.sf2"
            other_sf = sf_dir / "fallback.sf2"
            _write_fake_sf2(guitar_sf)
            _write_fake_sf2(other_sf)

            overrides = {"Piano": [], "Guitar": []}
            hints = {"Piano": ["*piano*.sf2"], "Guitar": ["*guitar*.sf2"]}
            with patch.object(config, "INSTRUMENT_ENV_OVERRIDES", overrides), patch.object(
                config, "COMMON_SOUNDFONT_LOCATIONS", []
            ), patch.object(config, "INSTRUMENT_FILENAME_HINTS", hints), patch.object(
                config, "SOUNDFONTS_DIR", sf_dir
            ):
                result = config.find_default_soundfont("Guitar")

            self.assertEqual(result, str(guitar_sf))

    def test_list_soundfont_candidates_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "shared.sf2"
            _write_fake_sf2(sf)

            overrides = {"Piano": [str(sf)], "Guitar": []}
            with patch.object(config, "INSTRUMENT_ENV_OVERRIDES", overrides), patch.object(
                config, "COMMON_SOUNDFONT_LOCATIONS", [str(sf)]
            ), patch.object(config, "SOUNDFONTS_DIR", Path(tmpdir)):
                candidates = config.list_soundfont_candidates("Piano")

            self.assertEqual(candidates, [str(sf)])

    def test_invalid_sf2_file_is_filtered_out(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_sf = Path(tmpdir) / "broken.sf2"
            bad_sf.write_text("<html>not a soundfont</html>", encoding="utf-8")

            with patch.object(config, "COMMON_SOUNDFONT_LOCATIONS", [str(bad_sf)]), patch.object(
                config, "INSTRUMENT_ENV_OVERRIDES", {"Piano": [], "Guitar": []}
            ), patch.object(config, "SOUNDFONTS_DIR", Path(tmpdir)):
                candidates = config.list_soundfont_candidates("Piano")

            self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
