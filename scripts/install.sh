#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

cat <<'EOF'
Warning: scripts/install.sh is kept for compatibility.
Use scripts/install_arch.sh (Arch Linux) or scripts/install_linux.sh (other Linux distros) instead.
EOF

if command -v pacman >/dev/null 2>&1 && [[ -f /etc/arch-release ]]; then
    exec bash "$root/scripts/install_arch.sh" "$@"
fi

exec bash "$root/scripts/install_linux.sh" "$@"
