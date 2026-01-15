#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

system_install=0
for arg in "$@"; do
    case "$arg" in
        --system)
            system_install=1
            ;;
        -h|--help)
            echo "Usage: $0 [--system]"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Usage: $0 [--system]" >&2
            exit 2
            ;;
    esac
done

venv_dir="$root/.venv"
python_bin="$venv_dir/bin/python"

if [[ ! -x "$python_bin" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv "$venv_dir"
    elif command -v python >/dev/null 2>&1; then
        python -m venv "$venv_dir"
    else
        echo "Error: python3 not found."
        exit 1
    fi
fi

"$python_bin" -m pip install -r "$root/requirements.txt"
if [[ "$system_install" -eq 1 ]]; then
    bash "$root/scripts/install_desktop.sh" --system
else
    bash "$root/scripts/install_desktop.sh"
fi

echo "Install complete."
