"""MIDI library folder management."""

from __future__ import annotations

import shutil
from pathlib import Path


class MidiLibraryService:
    """Manage discovery and ingestion of MIDI files for the library panel."""

    def __init__(self, midi_dir: Path):
        self._midi_dir = midi_dir

    @property
    def midi_dir(self) -> Path:
        return self._midi_dir

    def set_midi_dir(self, path: str | Path) -> None:
        self._midi_dir = Path(path).expanduser()

    def ensure_dir(self) -> None:
        self._midi_dir.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> list[str]:
        if not self._midi_dir.exists():
            return []
        return [
            str(path)
            for path in sorted(self._midi_dir.iterdir())
            if path.is_file() and path.suffix.lower() in (".mid", ".midi")
        ]

    def import_files(self, paths: list[str]) -> bool:
        if not paths:
            return False

        moved_any = False
        for path in paths:
            src = Path(path)
            if not src.exists() or src.suffix.lower() not in (".mid", ".midi"):
                continue
            try:
                if src.resolve().parent == self._midi_dir.resolve():
                    moved_any = True
                    continue
            except Exception:
                pass

            dest = self.unique_destination(src.name)
            try:
                shutil.move(str(src), str(dest))
                moved_any = True
            except Exception as exc:
                print(f"Failed to move '{src}' to '{dest}': {exc}")
        return moved_any

    def unique_destination(self, filename: str) -> Path:
        candidate = self._midi_dir / filename
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        for idx in range(1, 1000):
            alt = self._midi_dir / f"{stem}-{idx}{suffix}"
            if not alt.exists():
                return alt

        raise FileExistsError(f"Could not find unique filename for {filename}")
