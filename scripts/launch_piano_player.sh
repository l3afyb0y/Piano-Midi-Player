#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"
if [[ -n "${PIANO_PLAYER_USE_BINARY:-}" ]]; then
    app_name="Piano Player"
    binary="$root/dist/$app_name/$app_name"
    exec "$binary" "$@"
fi

if [[ -x "$root/.venv/bin/python" ]]; then
    exec "$root/.venv/bin/python" "$root/main.py" "$@"
fi

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$root/main.py" "$@"
fi

exec python "$root/main.py" "$@"
