#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"

use_dev_pkgbuild=0
makepkg_args=()

while (($#)); do
    case "$1" in
        --dev)
            use_dev_pkgbuild=1
            shift
            ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/install_arch.sh [--dev] [makepkg args...]

Build/install Piano Player from PKGBUILD.

Options:
  --dev   Use dev/PKGBUILD instead of the top-level PKGBUILD.

Examples:
  scripts/install_arch.sh
  scripts/install_arch.sh --dev
  scripts/install_arch.sh -- --cleanbuild
EOF
            exit 0
            ;;
        --)
            shift
            makepkg_args+=("$@")
            break
            ;;
        *)
            makepkg_args+=("$1")
            shift
            ;;
    esac
done

pkgbuild_dir="$root"
if [[ "$use_dev_pkgbuild" -eq 1 ]]; then
    pkgbuild_dir="$root/dev"
fi

if [[ ! -f "$pkgbuild_dir/PKGBUILD" ]]; then
    echo "Error: PKGBUILD not found at $pkgbuild_dir/PKGBUILD" >&2
    exit 1
fi

cd "$pkgbuild_dir"
exec makepkg -si "${makepkg_args[@]}"
