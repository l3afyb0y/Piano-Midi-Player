import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import piano_player.config as config


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


if __name__ == "__main__":
    unittest.main()
