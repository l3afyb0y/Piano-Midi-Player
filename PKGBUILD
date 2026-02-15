# Maintainer: Porker Roland <gitporker@gmail.com>

pkgname=piano-player-git
_pkgname=piano-player
pkgver=r25.gc99878f
pkgrel=1
pkgdesc='Desktop MIDI piano player/editor with recording and falling-note practice view'
arch=('any')
url='https://github.com/l3afyb0y/Piano-Midi-Player'
license=('MIT')
depends=(
  'python'
  'python-pyqt6'
  'python-numpy'
  'python-mido'
  'python-rtmidi'
  'portaudio'
)
optdepends=(
  'python-sounddevice: python sounddevice module (AUR) for realtime audio backend'
  'fluidsynth: high-quality SoundFont synthesis backend'
  'python-pyfluidsynth: Python FluidSynth bindings (AUR)'
)
makedepends=('git' 'p7zip')
source=(
  "git+${url}.git"
  "freepats-upright-piano-small-20190703.7z::https://freepats.zenvoid.org/Piano/UprightPianoKW/UprightPianoKW-small-SF2-20190703.7z"
  "freepats-electric-guitar-clean-small-20220911.7z::https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/EGuitarFSBS-bridge-clean-small-SF2-20220911.7z"
)
sha256sums=(
  'SKIP'
  '3bd025e7c2ffa9e6f3f99215ce383c9cebbac991cfbf9be1453cdb4328ec3492'
  '61f14af225c00d0621a57033f910ecdd8c2916752b7fd111744fa7eee3f05932'
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

  7z x -y "${srcdir}/freepats-upright-piano-small-20190703.7z" "-o${_sf_tmp}" >/dev/null
  7z x -y "${srcdir}/freepats-electric-guitar-clean-small-20220911.7z" "-o${_sf_tmp}" >/dev/null

  install -Dm644 "${_sf_tmp}/UprightPianoKW-small-SF2-20190703/UprightPianoKW-small-20190703.sf2" \
    "${pkgdir}/usr/share/${_pkgname}/soundfonts/UprightPianoKW-small-20190703.sf2"
  install -Dm644 "${_sf_tmp}/EGuitarFSBS-bridge-clean-small-SF2-20220911/EGuitarFSBS-bridge-clean-small-20220911.sf2" \
    "${pkgdir}/usr/share/${_pkgname}/soundfonts/EGuitarFSBS-bridge-clean-small-20220911.sf2"

  install -Dm644 "${_sf_tmp}/UprightPianoKW-small-SF2-20190703/cc0.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/UprightPianoKW-CC0.txt"
  install -Dm644 "${_sf_tmp}/EGuitarFSBS-bridge-clean-small-SF2-20220911/cc0.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/EGuitarFSBS-clean-CC0.txt"
  install -Dm644 "${_sf_tmp}/UprightPianoKW-small-SF2-20190703/readme.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/UprightPianoKW-readme.txt"
  install -Dm644 "${_sf_tmp}/EGuitarFSBS-bridge-clean-small-SF2-20220911/readme.txt" \
    "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/EGuitarFSBS-clean-readme.txt"

  if [ -f soundfonts/README.md ]; then
    install -Dm644 soundfonts/README.md \
      "${pkgdir}/usr/share/doc/${pkgname}/soundfonts/README-project.txt"
  fi

  for sf in soundfonts/*.sf2; do
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
}
