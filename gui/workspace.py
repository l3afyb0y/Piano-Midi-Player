"""Workspace presets for DAW-like panel layouts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspacePreset:
    key: str
    label: str
    sizes: tuple[int, int, int]
    description: str


WORKSPACE_PRESETS = (
    WorkspacePreset(
        key="balanced",
        label="Balanced",
        sizes=(220, 520, 110),
        description="Balanced split between library, piano roll, and transport.",
    ),
    WorkspacePreset(
        key="practice",
        label="Practice Focus",
        sizes=(110, 660, 80),
        description="Maximize piano roll and keyboard visibility for play-along.",
    ),
    WorkspacePreset(
        key="library",
        label="Library Focus",
        sizes=(460, 300, 100),
        description="Prioritize MIDI browser and import workflow.",
    ),
)


PRESET_BY_KEY = {preset.key: preset for preset in WORKSPACE_PRESETS}
