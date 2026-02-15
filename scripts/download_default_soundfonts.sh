#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
root="$(cd "$(dirname "$script_path")/.." && pwd)"
dest_dir="${root}/soundfonts"
force=0

while (($#)); do
    case "$1" in
        --force)
            force=1
            shift
            ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/download_default_soundfonts.sh [--force]

Download and install default CC0 SoundFonts used by Piano Player:
  - Upright Piano (FreePats)
  - Clean Electric Guitar (FreePats)

Options:
  --force   Re-download and overwrite existing defaults.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
done

if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl is required to download default SoundFonts." >&2
    exit 1
fi

if ! command -v 7z >/dev/null 2>&1; then
    echo "Error: 7z is required to extract default SoundFont archives." >&2
    exit 1
fi

mkdir -p "${dest_dir}"

piano_out="${dest_dir}/UprightPianoKW-small-20190703.sf2"
guitar_out="${dest_dir}/EGuitarFSBS-bridge-clean-small-20220911.sf2"

if [[ "${force}" -eq 0 && -f "${piano_out}" && -f "${guitar_out}" ]]; then
    echo "Default SoundFonts already present in ${dest_dir}."
    exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

piano_archive="${tmpdir}/piano.7z"
guitar_archive="${tmpdir}/guitar.7z"

piano_url="https://freepats.zenvoid.org/Piano/UprightPianoKW/UprightPianoKW-small-SF2-20190703.7z"
guitar_url="https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/EGuitarFSBS-bridge-clean-small-SF2-20220911.7z"
piano_sha256="3bd025e7c2ffa9e6f3f99215ce383c9cebbac991cfbf9be1453cdb4328ec3492"
guitar_sha256="61f14af225c00d0621a57033f910ecdd8c2916752b7fd111744fa7eee3f05932"

echo "Downloading default piano SoundFont..."
curl -fL --retry 3 --retry-delay 1 -o "${piano_archive}" "${piano_url}"
echo "${piano_sha256}  ${piano_archive}" | sha256sum -c -

echo "Downloading default clean electric guitar SoundFont..."
curl -fL --retry 3 --retry-delay 1 -o "${guitar_archive}" "${guitar_url}"
echo "${guitar_sha256}  ${guitar_archive}" | sha256sum -c -

echo "Extracting SoundFonts..."
7z x -y "${piano_archive}" "-o${tmpdir}" >/dev/null
7z x -y "${guitar_archive}" "-o${tmpdir}" >/dev/null

install -Dm644 \
    "${tmpdir}/UprightPianoKW-small-SF2-20190703/UprightPianoKW-small-20190703.sf2" \
    "${piano_out}"
install -Dm644 \
    "${tmpdir}/EGuitarFSBS-bridge-clean-small-SF2-20220911/EGuitarFSBS-bridge-clean-small-20220911.sf2" \
    "${guitar_out}"

install -Dm644 \
    "${tmpdir}/UprightPianoKW-small-SF2-20190703/cc0.txt" \
    "${dest_dir}/UprightPianoKW-CC0.txt"
install -Dm644 \
    "${tmpdir}/EGuitarFSBS-bridge-clean-small-SF2-20220911/cc0.txt" \
    "${dest_dir}/EGuitarFSBS-clean-CC0.txt"
install -Dm644 \
    "${tmpdir}/UprightPianoKW-small-SF2-20190703/readme.txt" \
    "${dest_dir}/UprightPianoKW-readme.txt"
install -Dm644 \
    "${tmpdir}/EGuitarFSBS-bridge-clean-small-SF2-20220911/readme.txt" \
    "${dest_dir}/EGuitarFSBS-clean-readme.txt"

echo "Installed default SoundFonts to ${dest_dir}."
