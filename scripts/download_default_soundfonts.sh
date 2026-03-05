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

Download and install default high-quality instrument packs used by Piano Player:
  - Acoustic Grand Piano: Salamander Grand Piano SFZ+FLAC (FreePats, CC-BY-3.0)
  - Clean Electric Guitar: FSBS bridge clean SFZ+FLAC (FreePats, CC0)

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
    echo "Error: curl is required to download default instrument packs." >&2
    exit 1
fi

if ! command -v 7z >/dev/null 2>&1; then
    echo "Error: 7z is required to extract default instrument archives." >&2
    exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
    echo "Error: tar is required to extract default instrument archives." >&2
    exit 1
fi

mkdir -p "${dest_dir}"

piano_dir="${dest_dir}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602"
piano_out="${piano_dir}/SalamanderGrandPiano-V3+20200602.sfz"
guitar_dir="${dest_dir}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911"
guitar_out="${guitar_dir}/EGuitarFSBS-bridge-clean-20220911.sfz"

if [[ "${force}" -eq 0 && -f "${piano_out}" && -f "${guitar_out}" ]]; then
    echo "Default instrument packs already present in ${dest_dir}."
    exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

piano_archive="${tmpdir}/piano.tar.gz"
guitar_archive="${tmpdir}/guitar.7z"

piano_url="https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPiano-SFZ+FLAC-V3+20200602.tar.gz"
guitar_url="https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911.7z"
piano_sha256="b7760e168494cf095344e217b0af013fc449ad033abbbdf1c65211cf11dc038b"
guitar_sha256="d371496bdb0622444e8956a65e85953257ef9eae9bb7cb6e675512e61deac17b"

echo "Downloading default acoustic grand piano instrument pack..."
curl -fL --retry 3 --retry-delay 1 -o "${piano_archive}" "${piano_url}"
echo "${piano_sha256}  ${piano_archive}" | sha256sum -c -

echo "Downloading default clean electric guitar instrument pack..."
curl -fL --retry 3 --retry-delay 1 -o "${guitar_archive}" "${guitar_url}"
echo "${guitar_sha256}  ${guitar_archive}" | sha256sum -c -

echo "Extracting instrument packs..."
tar -xzf "${piano_archive}" -C "${tmpdir}"
7z x -y "${guitar_archive}" "-o${tmpdir}" >/dev/null

rm -rf "${piano_dir}" "${guitar_dir}"
cp -a "${tmpdir}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602" "${dest_dir}/"
cp -a "${tmpdir}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911" "${dest_dir}/"

install -Dm644 \
    "${tmpdir}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602/readme.txt" \
    "${dest_dir}/SalamanderGrandPiano-readme-CC-BY-3.0.txt"
install -Dm644 \
    "${tmpdir}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911/cc0.txt" \
    "${dest_dir}/EGuitarFSBS-clean-CC0.txt"
install -Dm644 \
    "${tmpdir}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911/readme.txt" \
    "${dest_dir}/EGuitarFSBS-clean-readme.txt"

echo "Installed default instrument packs to ${dest_dir}."
