"""Shared instrument metadata and normalization helpers."""

from __future__ import annotations

DEFAULT_INSTRUMENT = "Piano"

SUPPORTED_INSTRUMENTS: tuple[str, ...] = (
    "Piano",
    "Guitar",
)

INSTRUMENT_LABELS: dict[str, str] = {
    "Piano": "Acoustic Grand Piano",
    "Guitar": "Clean Electric Guitar",
}


def normalize_instrument(value: str | None) -> str:
    """Return a supported instrument key with a safe default."""
    if value in SUPPORTED_INSTRUMENTS:
        return str(value)
    return DEFAULT_INSTRUMENT

