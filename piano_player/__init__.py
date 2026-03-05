"""Piano Player application package.

Keep package imports lightweight to avoid circular import issues when UI modules
import package submodules directly (e.g. ``piano_player.synth_modes``).
"""

from __future__ import annotations

from typing import Any

__all__ = ["PianoPlayerController"]


def __getattr__(name: str) -> Any:
    if name == "PianoPlayerController":
        from piano_player.controller import PianoPlayerController

        return PianoPlayerController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
