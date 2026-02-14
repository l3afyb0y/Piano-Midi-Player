import tempfile
import unittest
from pathlib import Path

from piano_player.services.midi_library import MidiLibraryService


class MidiLibraryServiceTests(unittest.TestCase):
    def test_list_files_filters_non_midi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.mid").write_bytes(b"x")
            (root / "b.midi").write_bytes(b"x")
            (root / "ignore.txt").write_text("x", encoding="utf-8")

            service = MidiLibraryService(root)
            files = service.list_files()

            self.assertEqual(len(files), 2)
            self.assertTrue(files[0].endswith("a.mid"))
            self.assertTrue(files[1].endswith("b.midi"))

    def test_import_files_renames_on_collision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library = root / "library"
            incoming = root / "incoming"
            library.mkdir()
            incoming.mkdir()

            (library / "song.mid").write_bytes(b"existing")
            dropped = incoming / "song.mid"
            dropped.write_bytes(b"new")

            service = MidiLibraryService(library)
            moved_any = service.import_files([str(dropped)])

            self.assertTrue(moved_any)
            self.assertFalse(dropped.exists())
            self.assertTrue((library / "song.mid").exists())
            self.assertTrue((library / "song-1.mid").exists())


if __name__ == "__main__":
    unittest.main()
