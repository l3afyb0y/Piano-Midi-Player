#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

system_install=0
python_cmd=""
install_default_soundfonts=1
install_system_audio_deps=1
for arg in "$@"; do
    case "$arg" in
        --system)
            system_install=1
            ;;
        --no-system-audio-deps)
            install_system_audio_deps=0
            ;;
        --no-default-soundfonts)
            install_default_soundfonts=0
            ;;
        --python=*)
            python_cmd="${arg#*=}"
            ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/install_linux.sh [--system] [--python=python3.x] [--no-system-audio-deps] [--no-default-soundfonts]

Sets up a local virtualenv, installs Python dependencies, and installs desktop launcher files.

Options:
  --system            Install desktop entry/launcher system-wide.
  --python=<binary>   Python executable used for venv creation.
  --no-system-audio-deps
                     Skip best-effort installation of system audio deps
                     (FluidSynth + sfizz when package manager support exists).
  --no-default-soundfonts
                     Skip downloading bundled default high-quality instrument packs.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

run_with_privileges() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
        return
    fi
    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
        return
    fi
    return 1
}

install_system_audio_dependencies() {
    if [[ "$install_system_audio_deps" -ne 1 ]]; then
        return 0
    fi

    if command -v pacman >/dev/null 2>&1 && [[ -f /etc/arch-release ]]; then
        run_with_privileges pacman -S --needed --noconfirm fluidsynth sfizz || true
        return 0
    fi
    if command -v apt-get >/dev/null 2>&1; then
        run_with_privileges apt-get update || true
        run_with_privileges apt-get install -y fluidsynth sfizz || run_with_privileges apt-get install -y fluidsynth || true
        return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
        run_with_privileges dnf install -y fluidsynth sfizz || run_with_privileges dnf install -y fluidsynth || true
        return 0
    fi
    if command -v zypper >/dev/null 2>&1; then
        run_with_privileges zypper --non-interactive install fluidsynth sfizz || run_with_privileges zypper --non-interactive install fluidsynth || true
        return 0
    fi

    echo "Warning: unsupported package manager for auto-installing audio deps (fluidsynth/sfizz)." >&2
    return 0
}

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

install_system_audio_dependencies

venv_dir="$root/.venv"
python_bin="$venv_dir/bin/python"

if [[ ! -x "$python_bin" ]]; then
    "$python_cmd" -m venv "$venv_dir"
fi

"$python_bin" -m pip install --upgrade pip
"$python_bin" -m pip install -r "$root/requirements.txt"

if [[ "$install_default_soundfonts" -eq 1 ]]; then
    if ! bash "$root/scripts/download_default_soundfonts.sh"; then
        echo "Warning: failed to install default instrument packs. You can retry with scripts/download_default_soundfonts.sh" >&2
    fi
fi

if [[ "$system_install" -eq 1 ]]; then
    bash "$root/scripts/install_desktop.sh" --system
else
    bash "$root/scripts/install_desktop.sh"
fi

echo "Linux install complete. Run with: $python_bin $root/main.py"
