#!/usr/bin/env python3
"""Build a standalone app using PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build():
    root = Path(__file__).resolve().parents[1]
    app_name = "Piano Player"

    data_args = []
    soundfonts_dir = root / "soundfonts"
    if soundfonts_dir.exists():
        separator = ";" if sys.platform.startswith("win") else ":"
        data_args = ["--add-data", f"{soundfonts_dir}{separator}soundfonts"]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        app_name,
        *data_args,
        str(root / "main.py"),
    ]

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(root))


if __name__ == "__main__":
    build()
