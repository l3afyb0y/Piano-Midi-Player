#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
launcher="$root/scripts/launch_piano_player.sh"
desktop_src="$root/piano-player.desktop"
desktop_dst="$apps_dir/piano-player.desktop"

mkdir -p "$bin_dir" "$apps_dir"
ln -sf "$launcher" "$bin_dir/piano-player"
cp "$desktop_src" "$desktop_dst"
sed -i "s|^Exec=.*|Exec=$bin_dir/piano-player|" "$desktop_dst"

rm -f "$HOME/.cache/rofi3.druncache"
find "$HOME/.cache" -maxdepth 1 -type d -name 'rofi*' -exec rm -f {}/drun\* \; 2>/dev/null || true

printf "Installed launcher: %s\n" "$bin_dir/piano-player"
printf "Installed desktop entry: %s\n" "$desktop_dst"
