"""Application-wide configuration and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOUNDFONTS_DIR = PROJECT_DIR / "soundfonts"
CONFIG_DIR = Path.home() / ".config" / "piano-player"
DEFAULT_MIDI_DIR = CONFIG_DIR / "MIDI"
LEGACY_MIDI_DIR = Path.home() / "midi"

DEFAULT_SOUNDFONT_LOCATIONS = [
    os.environ.get("PIANO_PLAYER_SOUNDFONT"),
    os.environ.get("SOUNDFONT_PATH"),
    str(SOUNDFONTS_DIR / "default.sf2"),
    str(SOUNDFONTS_DIR / "FluidR3_GM.sf2"),
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/Library/Audio/Sounds/Banks/FluidR3_GM.sf2",
]


def find_default_soundfont() -> str | None:
    """Return the first usable SoundFont path if one is available."""
    for candidate in DEFAULT_SOUNDFONT_LOCATIONS:
        if candidate and os.path.exists(candidate):
            return candidate

    if SOUNDFONTS_DIR.is_dir():
        for path in sorted(SOUNDFONTS_DIR.glob("*.sf2")):
            return str(path)

    return None


def resolve_midi_directory(saved_path: str | None) -> Path:
    """Resolve MIDI library path with backward-compatible migration behavior."""
    if saved_path:
        return Path(saved_path).expanduser()

    # Preserve existing users' libraries when they already use ~/midi.
    if LEGACY_MIDI_DIR.is_dir():
        has_midi = any(
            p.is_file() and p.suffix.lower() in (".mid", ".midi")
            for p in LEGACY_MIDI_DIR.iterdir()
        )
        if has_midi:
            return LEGACY_MIDI_DIR

    return DEFAULT_MIDI_DIR
