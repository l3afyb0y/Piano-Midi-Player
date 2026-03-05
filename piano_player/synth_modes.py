"""Shared synthesizer mode labels and normalization helpers."""

from __future__ import annotations

SYNTH_SIMPLE = "Simple Synth"
SYNTH_SF2 = "SF2 (FluidSynth)"
SYNTH_SFZ = "SFZ (sfizz)"

SAMPLED_SYNTHS = (SYNTH_SF2, SYNTH_SFZ)
ALL_SYNTHS = (SYNTH_SIMPLE, SYNTH_SF2, SYNTH_SFZ)

LEGACY_MODE_ALIASES = {
    "SoundFont": SYNTH_SFZ,
}


def normalize_synth_mode(value: str | None) -> str:
    if value in ALL_SYNTHS:
        return str(value)
    return LEGACY_MODE_ALIASES.get(str(value), SYNTH_SFZ)
