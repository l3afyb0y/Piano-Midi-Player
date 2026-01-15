#!/usr/bin/env python3
"""Self-test for Piano Player dependencies and device access."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Tuple


def run_snippet(code: str, timeout: float, cwd: Path) -> Tuple[bool, str, str]:
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"timeout after {timeout}s"

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        return False, stdout, stderr
    return True, stdout, stderr


def check_import(module: str, timeout: float, cwd: Path) -> Tuple[bool, str]:
    code = (
        "import importlib\n"
        f"importlib.import_module({module!r})\n"
        "print('ok')\n"
    )
    ok, stdout, stderr = run_snippet(code, timeout, cwd)
    if ok:
        return True, "ok"
    detail = stderr or stdout or "import failed"
    return False, detail


def find_soundfont(repo_root: Path) -> str | None:
    for env_var in ("PIANO_PLAYER_SOUNDFONT", "SOUNDFONT_PATH"):
        value = os.environ.get(env_var)
        if value and Path(value).exists():
            return value

    soundfonts_dir = repo_root / "soundfonts"
    if soundfonts_dir.is_dir():
        for path in sorted(soundfonts_dir.glob("*.sf2")):
            return str(path)
    return None


def check_sounddevice(timeout: float, cwd: Path) -> Tuple[bool, str]:
    code = (
        "import sounddevice as sd\n"
        "devices = sd.query_devices()\n"
        "outputs = [d for d in devices if d.get('max_output_channels', 0) > 0]\n"
        "print(len(outputs))\n"
        "if outputs:\n"
        "    print(sd.default.device)\n"
    )
    ok, stdout, stderr = run_snippet(code, timeout, cwd)
    if not ok:
        return False, stderr or stdout or "sounddevice query failed"
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return False, "sounddevice returned no output"
    try:
        output_count = int(lines[0])
    except ValueError:
        return False, f"unexpected sounddevice output: {stdout}"
    if output_count <= 0:
        return False, "no audio output devices detected"
    return True, f"{output_count} output device(s) detected"


def check_sounddevice_beep(timeout: float, cwd: Path) -> Tuple[bool, str]:
    code = (
        "import numpy as np\n"
        "import sounddevice as sd\n"
        "samplerate = 44100\n"
        "duration = 0.25\n"
        "t = np.linspace(0.0, duration, int(samplerate * duration), False)\n"
        "samples = 0.12 * np.sin(2 * np.pi * 440 * t).astype(np.float32)\n"
        "sd.play(samples, samplerate=samplerate, blocking=True)\n"
        "print('ok')\n"
    )
    ok, stdout, stderr = run_snippet(code, timeout, cwd)
    if ok:
        return True, "beep played (verify audibly)"
    return False, stderr or stdout or "beep failed"


def check_midi_ports(timeout: float, cwd: Path) -> Tuple[bool, str, str]:
    code = (
        "import rtmidi\n"
        "midi = rtmidi.MidiIn()\n"
        "ports = midi.get_ports()\n"
        "print(len(ports))\n"
        "for port in ports:\n"
        "    print(port)\n"
    )
    ok, stdout, stderr = run_snippet(code, timeout, cwd)
    if not ok:
        return False, stderr or stdout or "MIDI port scan failed", ""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return False, "unexpected MIDI output", ""
    try:
        count = int(lines[0])
    except ValueError:
        return False, f"unexpected MIDI output: {stdout}", ""
    ports = "\n".join(lines[1:])
    if count == 0:
        return True, "no MIDI input ports detected", ports
    return True, f"{count} MIDI input port(s) detected", ports


def check_soundfont_load(timeout: float, cwd: Path, soundfont_path: str) -> Tuple[bool, str]:
    code = (
        "from audio.soundfont_synth import SoundFontSynth\n"
        f"soundfont = {soundfont_path!r}\n"
        "synth = SoundFontSynth()\n"
        "ok = synth.load_soundfont(soundfont)\n"
        "print('ok' if ok else 'fail')\n"
        "synth.cleanup()\n"
    )
    ok, stdout, stderr = run_snippet(code, timeout, cwd)
    if not ok:
        return False, stderr or stdout or "SoundFont load failed"
    if stdout.strip().endswith("ok"):
        return True, "SoundFont loaded"
    return False, stdout or "SoundFont load failed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Piano Player self-test")
    parser.add_argument("--beep", action="store_true", help="play a short test tone")
    parser.add_argument("--list-devices", action="store_true", help="print audio devices")
    parser.add_argument("--list-midi", action="store_true", help="print MIDI ports")
    parser.add_argument("--load-soundfont", action="store_true", help="attempt to load a SoundFont")
    parser.add_argument("--timeout", type=float, default=5.0, help="timeout seconds per check")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv:
        print("Warning: virtualenv not detected; activate .venv for accurate results.")
    home = Path.home()
    if repo_root.is_relative_to(home):
        repo_display = f"~/{repo_root.relative_to(home)}"
    else:
        repo_display = str(repo_root)
    print(f"Repo: {repo_display}")

    checks = []
    for module in ("PyQt6", "sounddevice", "mido", "rtmidi", "fluidsynth"):
        ok, detail = check_import(module, args.timeout, repo_root)
        checks.append((f"import {module}", ok, detail))

    ok, detail = check_sounddevice(args.timeout, repo_root)
    checks.append(("sounddevice output device", ok, detail))

    if args.beep:
        ok, detail = check_sounddevice_beep(args.timeout, repo_root)
        checks.append(("sounddevice beep", ok, detail))

    midi_ok, midi_detail, midi_ports = check_midi_ports(args.timeout, repo_root)
    checks.append(("rtmidi ports", midi_ok, midi_detail))

    if args.list_devices:
        ok, stdout, stderr = run_snippet(
            "import sounddevice as sd\nprint(sd.query_devices())\n",
            args.timeout,
            repo_root,
        )
        if ok:
            print("\nAudio devices:")
            print(stdout)
        else:
            print("\nAudio devices: failed")
            if stderr:
                print(stderr)

    if args.list_midi:
        print("\nMIDI ports:")
        print(midi_ports or "(none)")

    if args.load_soundfont:
        soundfont_path = find_soundfont(repo_root)
        if not soundfont_path:
            checks.append(("SoundFont load", False, "no .sf2 found"))
        else:
            ok, detail = check_soundfont_load(args.timeout, repo_root, soundfont_path)
            checks.append(("SoundFont load", ok, f"{detail}: {soundfont_path}"))

    print("\nResults:")
    failed = False
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed = True
        print(f"- {status}: {name} ({detail})")

    if failed:
        print("\nSelf-test failed; check the messages above.")
        return 1
    print("\nSelf-test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
