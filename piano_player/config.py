"""Application-wide configuration and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

from piano_player.instruments import DEFAULT_INSTRUMENT, SUPPORTED_INSTRUMENTS

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOUNDFONTS_DIR = PROJECT_DIR / "soundfonts"
CONFIG_DIR = Path.home() / ".config" / "piano-player"
DEFAULT_MIDI_DIR = CONFIG_DIR / "MIDI"
LEGACY_MIDI_DIR = Path.home() / "midi"
SYSTEM_SOUNDFONTS_DIR = Path("/usr/share/piano-player/soundfonts")
USER_SOUNDFONTS_DIR = CONFIG_DIR / "soundfonts"

COMMON_SOUNDFONT_LOCATIONS = [
    os.environ.get("PIANO_PLAYER_SOUNDFONT"),
    os.environ.get("PIANO_PLAYER_SFZ"),
    os.environ.get("SOUNDFONT_PATH"),
    "/usr/share/piano-player/soundfonts/SalamanderGrandPiano-SFZ+FLAC-V3+20200602/SalamanderGrandPiano-V3+20200602.sfz",
    "/usr/share/piano-player/soundfonts/UprightPianoKW-small-20190703.sf2",
    str(
        SOUNDFONTS_DIR
        / "SalamanderGrandPiano-SFZ+FLAC-V3+20200602"
        / "SalamanderGrandPiano-V3+20200602.sfz"
    ),
    str(SOUNDFONTS_DIR / "UprightPianoKW-small-20190703.sf2"),
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

def _soundfont_search_dirs() -> list[Path]:
    return [
        SOUNDFONTS_DIR,
        USER_SOUNDFONTS_DIR,
        SYSTEM_SOUNDFONTS_DIR,
    ]

INSTRUMENT_ENV_OVERRIDES = {
    "Piano": [
        os.environ.get("PIANO_PLAYER_SOUNDFONT_PIANO"),
        os.environ.get("PIANO_PLAYER_SFZ_PIANO"),
    ],
    "Guitar": [
        os.environ.get("PIANO_PLAYER_SOUNDFONT_GUITAR"),
        os.environ.get("PIANO_PLAYER_SFZ_GUITAR"),
    ],
}

INSTRUMENT_FILENAME_HINTS = {
    "Piano": [
        "*piano*.sf2",
        "*grand*.sf2",
        "*steinway*.sf2",
        "*piano*.sfz",
        "*grand*.sfz",
        "*steinway*.sfz",
    ],
    "Guitar": [
        "*guitar*.sf2",
        "*nylon*.sf2",
        "*steel*.sf2",
        "*classical*.sf2",
        "*guitar*.sfz",
        "*nylon*.sfz",
        "*steel*.sfz",
        "*electric*.sfz",
    ],
}

INSTRUMENT_PREFERRED_FILENAMES = {
    "Piano": [
        "SalamanderGrandPiano-SFZ+FLAC-V3+20200602/SalamanderGrandPiano-V3+20200602.sfz",
        "UprightPianoKW-small-20190703.sf2",
        "GeneralUser GS v1.471.sf2",
        "GeneralUser_GS_v1.471.sf2",
        "Arachno SoundFont - Version 1.0.sf2",
    ],
    "Guitar": [
        "EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911/EGuitarFSBS-bridge-clean-20220911.sfz",
        "EGuitarFSBS-bridge-clean-small-20220911.sf2",
        "Timbres Of Heaven (XGM) 4.0.sf2",
        "Timbres Of Heaven GM_GS_XG_SFX V 3.4 Final.sf2",
        "Arachno SoundFont - Version 1.0.sf2",
        "GeneralUser GS v1.471.sf2",
        "GeneralUser_GS_v1.471.sf2",
    ],
}

def _candidate_matches_instrument(path: str, instrument: str) -> bool:
    """Heuristic filter to keep instrument lists relevant by default."""
    name = Path(path).name.lower()

    generic_tokens = ("fluidr3", "timgm", "generaluser", "arachno", "timbres", "gm")
    if any(token in name for token in generic_tokens):
        return True

    if instrument == "Piano":
        if "retuned" in name:
            return False
        if any(token in name for token in ("guitar", "eguitar", "electric")):
            return False
        return any(token in name for token in ("piano", "grand", "upright", "salamander", "steinway"))

    if instrument == "Guitar":
        if any(token in name for token in ("piano", "grand", "upright", "salamander", "steinway")):
            return False
        return any(token in name for token in ("guitar", "eguitar", "electric", "nylon", "steel"))

    return True


def _iter_dir_soundfont_files(directory: Path):
    """Yield .sf2/.sfz files from directory and one nested level.

    We intentionally avoid deep recursive scans because large SFZ packs include
    tens of thousands of sample files. The SFZ/SF2 definition files are expected
    at pack root or one level below.
    """
    if not directory.is_dir():
        return

    patterns = ("*.sf2", "*.sfz")
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            yield path

    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        for pattern in patterns:
            for path in sorted(child.glob(pattern)):
                yield path


def _iter_instrument_hints(search_dir: Path, patterns: list[str]):
    """Yield hint-matching files from search dir + one nested level."""
    if not search_dir.is_dir():
        return

    for pattern in patterns:
        for path in sorted(search_dir.glob(pattern)):
            yield path

    for child in sorted(search_dir.iterdir()):
        if not child.is_dir():
            continue
        for pattern in patterns:
            for path in sorted(child.glob(pattern)):
                yield path


def is_valid_soundfont_file(path: str | Path | None) -> bool:
    """Return True when file looks like a valid SF2 or SFZ instrument file."""
    if not path:
        return False
    target = Path(path).expanduser()
    if not target.is_file():
        return False

    suffix = target.suffix.lower()
    if suffix == ".sfz":
        # SFZ is text-based; minimal validation keeps us from rejecting valid custom files.
        try:
            with target.open("rb") as handle:
                chunk = handle.read(4096)
        except OSError:
            return False
        if not chunk:
            return False
        if b"\x00" in chunk:
            return False
        return True

    if suffix != ".sf2":
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
    instrument = instrument if instrument in SUPPORTED_INSTRUMENTS else DEFAULT_INSTRUMENT
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(candidate: str | None, apply_instrument_filter: bool = True):
        if not candidate:
            return
        resolved = str(Path(candidate).expanduser())
        if not is_valid_soundfont_file(resolved):
            return
        if apply_instrument_filter and not _candidate_matches_instrument(resolved, instrument):
            return
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(resolved)

    for candidate in INSTRUMENT_ENV_OVERRIDES.get(instrument, []):
        _append(candidate, apply_instrument_filter=False)

    for search_dir in _soundfont_search_dirs():
        if not search_dir.is_dir():
            continue
        for filename in INSTRUMENT_PREFERRED_FILENAMES.get(instrument, []):
            _append(str(search_dir / filename))

        hints = INSTRUMENT_FILENAME_HINTS.get(instrument, [])
        for path in _iter_instrument_hints(search_dir, hints):
            _append(str(path))

        for path in _iter_dir_soundfont_files(search_dir):
            _append(str(path))

    # Last-resort generic fallbacks.
    for candidate in COMMON_SOUNDFONT_LOCATIONS:
        _append(candidate)

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
