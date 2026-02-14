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
makedepends=('git')
source=("git+${url}.git")
sha256sums=('SKIP')

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
  if [ -d soundfonts ] && [ "$(ls -A soundfonts)" ]; then
    cp -r soundfonts/* "${pkgdir}/usr/share/${_pkgname}/soundfonts/"
  fi

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
