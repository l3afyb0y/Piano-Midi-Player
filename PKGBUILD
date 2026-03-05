# Maintainer: Porker Roland <gitporker@gmail.com>

pkgname=piano-player-git
_pkgname=piano-player
pkgver=r25.gc99878f
pkgrel=1
pkgdesc='Desktop MIDI piano player/editor with recording and falling-note practice view'
arch=('any')
url='https://github.com/l3afyb0y/Piano-Midi-Player'
license=('MIT' 'CC0-1.0' 'CC-BY-3.0')
provides=('piano-player')
conflicts=('piano-player')
depends=(
  'python'
  'python-pyqt6'
  'python-numpy'
  'python-mido'
  'python-rtmidi'
  'portaudio'
  'sfizz-lib'
)
optdepends=(
  'python-sounddevice: python sounddevice module (AUR) for realtime audio backend'
  'fluidsynth: high-quality SoundFont synthesis backend'
  'python-pyfluidsynth: Python FluidSynth bindings (AUR)'
)
makedepends=('git' 'p7zip')
source=(
  "git+${url}.git"
  "freepats-salamander-grand-piano-sfz-flac-20200602.tar.gz::https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPiano-SFZ+FLAC-V3+20200602.tar.gz"
  "freepats-electric-guitar-clean-sfz-flac-20220911.7z::https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911.7z"
)
sha256sums=(
  'SKIP'
  'b7760e168494cf095344e217b0af013fc449ad033abbbdf1c65211cf11dc038b'
  'd371496bdb0622444e8956a65e85953257ef9eae9bb7cb6e675512e61deac17b'
)

pkgver() {
  cd "${srcdir}/Piano-Midi-Player"
  printf 'r%s.g%s' "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  cd "${srcdir}/Piano-Midi-Player"

  install -d "${pkgdir}/usr/share/${_pkgname}"
  
  # Copy application directories
  for dir in audio gui midi piano_player recording; do
    if [ -d "$dir" ]; then
      cp -r "$dir" "${pkgdir}/usr/share/${_pkgname}/"
    fi
  done

  # Ensure soundfonts directory exists (even if empty in repo)
  install -d "${pkgdir}/usr/share/${_pkgname}/soundfonts"
  install -d "${pkgdir}/usr/share/doc/${pkgname}/soundfonts"

  local _sf_tmp="${srcdir}/_soundfonts_extract"
  rm -rf "${_sf_tmp}"
  mkdir -p "${_sf_tmp}"

  tar -xzf "${srcdir}/freepats-salamander-grand-piano-sfz-flac-20200602.tar.gz" -C "${_sf_tmp}"
  7z x -y "${srcdir}/freepats-electric-guitar-clean-sfz-flac-20220911.7z" "-o${_sf_tmp}" >/dev/null

  cp -a "${_sf_tmp}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602" \
    "${pkgdir}/usr/share/${_pkgname}/soundfonts/"
  cp -a "${_sf_tmp}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911" \
    "${pkgdir}/usr/share/${_pkgname}/soundfonts/"

  install -Dm644 "${_sf_tmp}/SalamanderGrandPiano-SFZ+FLAC-V3+20200602/readme.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/SalamanderGrandPiano-readme-CC-BY-3.0.txt"
  install -Dm644 "${_sf_tmp}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911/cc0.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/EGuitarFSBS-clean-CC0.txt"
  install -Dm644 "${_sf_tmp}/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911/readme.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/EGuitarFSBS-clean-readme.txt"

  if [ -f soundfonts/README.md ]; then
    install -Dm644 soundfonts/README.md \
      "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/README-project.txt"
  fi

  for sf in soundfonts/*.sf2 soundfonts/*.sfz; do
    if [ -f "${sf}" ]; then
      install -Dm644 "${sf}" "${pkgdir}/usr/share/${_pkgname}/soundfonts/$(basename "${sf}")"
    fi
  done

  install -Dm644 main.py "${pkgdir}/usr/share/${_pkgname}/main.py"

  install -d "${pkgdir}/usr/bin"
  cat > "${pkgdir}/usr/bin/piano-player" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python /usr/share/piano-player/main.py "$@"
EOF
  chmod 755 "${pkgdir}/usr/bin/piano-player"

  install -Dm644 piano-player.desktop "${pkgdir}/usr/share/applications/piano-player.desktop"
  sed -i 's|^Exec=.*|Exec=piano-player|' "${pkgdir}/usr/share/applications/piano-player.desktop"
  install -Dm644 assets/piano-player.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/piano-player.svg"
  install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
  install -Dm644 THIRD_PARTY_LICENSES.md "${pkgdir}/usr/share/doc/${pkgname}/THIRD_PARTY_LICENSES.md"
}
