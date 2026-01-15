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

if [[ "$system_install" -eq 1 ]]; then
    bin_dir="/usr/local/bin"
    apps_dir="/usr/local/share/applications"
    icons_root="/usr/local/share/icons"
else
    bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
    apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    icons_root="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
fi

sudo_cmd=""
if [[ "$system_install" -eq 1 && "${EUID:-$(id -u)}" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        sudo_cmd="sudo"
    else
        echo "Error: sudo is required for --system installs." >&2
        exit 1
    fi
fi

run_cmd() {
    if [[ -n "$sudo_cmd" ]]; then
        sudo "$@"
    else
        "$@"
    fi
}

launcher="$root/scripts/launch_piano_player.sh"
desktop_src="$root/piano-player.desktop"
desktop_dst="$apps_dir/piano-player.desktop"
icon_src="$root/assets/piano-player.svg"
icon_theme_dir="$icons_root/hicolor"
icon_dir="$icon_theme_dir/scalable/apps"
icon_dst="$icon_dir/piano-player.svg"
icon_installed=0

run_cmd mkdir -p "$bin_dir" "$apps_dir"
run_cmd ln -sf "$launcher" "$bin_dir/piano-player"
run_cmd cp "$desktop_src" "$desktop_dst"
run_cmd sed -i "s|^Exec=.*|Exec=$bin_dir/piano-player|" "$desktop_dst"

if [[ -f "$icon_src" ]]; then
    run_cmd mkdir -p "$icon_dir"
    run_cmd cp "$icon_src" "$icon_dst"
    icon_installed=1
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        run_cmd gtk-update-icon-cache -f -t "$icon_theme_dir"
    fi
else
    echo "Warning: icon source not found at $icon_src"
fi

if [[ "$system_install" -eq 0 ]]; then
    rm -f "$HOME/.cache/rofi3.druncache"
    find "$HOME/.cache" -maxdepth 1 -type d -name 'rofi*' -exec rm -f {}/drun\* \; 2>/dev/null || true
fi

printf "Installed launcher: %s\n" "$bin_dir/piano-player"
printf "Installed desktop entry: %s\n" "$desktop_dst"
if [[ "$icon_installed" -eq 1 ]]; then
    printf "Installed icon: %s\n" "$icon_dst"
else
    echo "Icon not installed."
fi
if [[ "$system_install" -eq 1 ]]; then
    echo "If the launcher does not appear, refresh your app launcher cache."
fi
