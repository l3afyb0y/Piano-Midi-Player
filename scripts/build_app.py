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

    paths_args = []
    venv_cfg = root / ".venv" / "pyvenv.cfg"
    if venv_cfg.exists():
        venv_version = None
        for line in venv_cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("version"):
                _, venv_version = line.split("=", 1)
                venv_version = venv_version.strip()
                break
        if venv_version:
            major_minor = ".".join(venv_version.split(".")[:2])
            site_packages = root / ".venv" / "lib" / f"python{major_minor}" / "site-packages"
            if site_packages.exists():
                paths_args.extend(["--paths", str(site_packages)])

    hidden_imports = ["PyQt6.sip"]
    hidden_args = []
    for hidden in hidden_imports:
        hidden_args.extend(["--hidden-import", hidden])

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        app_name,
        *paths_args,
        *hidden_args,
        *data_args,
        str(root / "main.py"),
    ]

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(root))


if __name__ == "__main__":
    build()
