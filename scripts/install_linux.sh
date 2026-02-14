#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

system_install=0
python_cmd=""
for arg in "$@"; do
    case "$arg" in
        --system)
            system_install=1
            ;;
        --python=*)
            python_cmd="${arg#*=}"
            ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/install_linux.sh [--system] [--python=python3.x]

Sets up a local virtualenv, installs Python dependencies, and installs desktop launcher files.

Options:
  --system            Install desktop entry/launcher system-wide.
  --python=<binary>   Python executable used for venv creation.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

if [[ -z "$python_cmd" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        python_cmd="python3"
    elif command -v python >/dev/null 2>&1; then
        python_cmd="python"
    else
        echo "Error: python not found." >&2
        exit 1
    fi
fi

venv_dir="$root/.venv"
python_bin="$venv_dir/bin/python"

if [[ ! -x "$python_bin" ]]; then
    "$python_cmd" -m venv "$venv_dir"
fi

"$python_bin" -m pip install --upgrade pip
"$python_bin" -m pip install -r "$root/requirements.txt"

if [[ "$system_install" -eq 1 ]]; then
    bash "$root/scripts/install_desktop.sh" --system
else
    bash "$root/scripts/install_desktop.sh"
fi

echo "Linux install complete. Run with: $python_bin $root/main.py"
