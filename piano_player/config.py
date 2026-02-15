"""Application-wide configuration and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOUNDFONTS_DIR = PROJECT_DIR / "soundfonts"
CONFIG_DIR = Path.home() / ".config" / "piano-player"
DEFAULT_MIDI_DIR = CONFIG_DIR / "MIDI"
LEGACY_MIDI_DIR = Path.home() / "midi"

COMMON_SOUNDFONT_LOCATIONS = [
    os.environ.get("PIANO_PLAYER_SOUNDFONT"),
    os.environ.get("SOUNDFONT_PATH"),
    str(SOUNDFONTS_DIR / "UprightPianoKW-small-20190703.sf2"),
    str(SOUNDFONTS_DIR / "EGuitarFSBS-bridge-clean-small-20220911.sf2"),
    str(SOUNDFONTS_DIR / "default.sf2"),
    str(SOUNDFONTS_DIR / "FluidR3_GM.sf2"),
    str(SOUNDFONTS_DIR / "GeneralUser GS v1.471.sf2"),
    str(SOUNDFONTS_DIR / "GeneralUser_GS_v1.471.sf2"),
    str(SOUNDFONTS_DIR / "Arachno SoundFont - Version 1.0.sf2"),
    str(SOUNDFONTS_DIR / "Timbres Of Heaven (XGM) 4.0.sf2"),
    str(SOUNDFONTS_DIR / "Timbres Of Heaven GM_GS_XG_SFX V 3.4 Final.sf2"),
    str(SOUNDFONTS_DIR / "GM_GS_Miscellaneous.sf2"),
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/Library/Audio/Sounds/Banks/FluidR3_GM.sf2",
]

INSTRUMENT_ENV_OVERRIDES = {
    "Piano": [
        os.environ.get("PIANO_PLAYER_SOUNDFONT_PIANO"),
    ],
    "Guitar": [
        os.environ.get("PIANO_PLAYER_SOUNDFONT_GUITAR"),
    ],
}

INSTRUMENT_FILENAME_HINTS = {
    "Piano": ["*piano*.sf2", "*grand*.sf2", "*steinway*.sf2"],
    "Guitar": ["*guitar*.sf2", "*nylon*.sf2", "*steel*.sf2", "*classical*.sf2"],
}

INSTRUMENT_PREFERRED_FILENAMES = {
    "Piano": [
        "UprightPianoKW-small-20190703.sf2",
        "GeneralUser GS v1.471.sf2",
        "GeneralUser_GS_v1.471.sf2",
        "Arachno SoundFont - Version 1.0.sf2",
    ],
    "Guitar": [
        "EGuitarFSBS-bridge-clean-small-20220911.sf2",
        "Timbres Of Heaven (XGM) 4.0.sf2",
        "Timbres Of Heaven GM_GS_XG_SFX V 3.4 Final.sf2",
        "Arachno SoundFont - Version 1.0.sf2",
        "GeneralUser GS v1.471.sf2",
        "GeneralUser_GS_v1.471.sf2",
    ],
}


def is_valid_soundfont_file(path: str | Path | None) -> bool:
    """Return True when file looks like a valid SF2 RIFF SoundFont."""
    if not path:
        return False
    target = Path(path).expanduser()
    if not target.is_file() or target.suffix.lower() != ".sf2":
        return False
    try:
        with target.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    if len(header) < 12:
        return False
    return header[:4] == b"RIFF" and header[8:12] == b"sfbk"


def list_soundfont_candidates(instrument: str = "Piano") -> list[str]:
    """Return ordered existing SoundFont paths for the requested instrument."""
    instrument = instrument if instrument in ("Piano", "Guitar") else "Piano"
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(candidate: str | None):
        if not candidate:
            return
        resolved = str(Path(candidate).expanduser())
        if not is_valid_soundfont_file(resolved):
            return
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(resolved)

    for candidate in INSTRUMENT_ENV_OVERRIDES.get(instrument, []):
        _append(candidate)

    for candidate in COMMON_SOUNDFONT_LOCATIONS:
        _append(candidate)

    if SOUNDFONTS_DIR.is_dir():
        for filename in INSTRUMENT_PREFERRED_FILENAMES.get(instrument, []):
            _append(str(SOUNDFONTS_DIR / filename))
        for pattern in INSTRUMENT_FILENAME_HINTS.get(instrument, []):
            for path in sorted(SOUNDFONTS_DIR.glob(pattern)):
                _append(str(path))
        for path in sorted(SOUNDFONTS_DIR.glob("*.sf2")):
            _append(str(path))

    return candidates


def find_default_soundfont(instrument: str = "Piano") -> str | None:
    """Return the first usable SoundFont path for the requested instrument."""
    candidates = list_soundfont_candidates(instrument)
    if candidates:
        return candidates[0]

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
