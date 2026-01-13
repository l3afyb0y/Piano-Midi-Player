#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"
app_name="Piano Player"
binary="$root/dist/$app_name/$app_name"

needs_build=0
if [[ ! -x "$binary" ]]; then
    needs_build=1
else
    if find "$root" \
        -path "$root/.git" -prune -o \
        -path "$root/.venv" -prune -o \
        -path "$root/build" -prune -o \
        -path "$root/dist" -prune -o \
        -path "$root/__pycache__" -prune -o \
        -path "$root/.worktrees" -prune -o \
        -type f \( -name '*.py' -o -name 'requirements*.txt' -o -name '*.sf2' -o -name 'piano-player.desktop' \) \
        -newer "$binary" -print -quit | grep -q .; then
        needs_build=1
    fi
fi

if [[ "$needs_build" -eq 1 ]]; then
    python "$root/scripts/build_app.py"
fi

exec "$binary" "$@"
