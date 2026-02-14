# Documentation

## Build and distribution
- `docs/BUILD.md`: PyInstaller build and launcher notes.

## Packaging and install
- `PKGBUILD`: Arch/AUR source package definition.
- `dev/PKGBUILD`: local development package definition (build from current working tree).
- `.SRCINFO`: generated metadata for AUR uploads.
- `piano-player.desktop`: launcher metadata installed by package.
- `scripts/install_arch.sh`: convenience wrapper around `makepkg -si` (`--dev` uses `dev/PKGBUILD`).
- `scripts/install_linux.sh`: Generic Linux installer.
- `scripts/install.sh`: Compatibility wrapper.

## Design notes
- `docs/plans/2026-01-02-piano-player-design.md`: original product/design notes.
- `docs/plans/2026-01-02-piano-player-implementation.md`: initial implementation plan.
- `docs/plans/2026-01-11-piano-roll-editor-design.md`: piano-roll editing design notes.

## Current UI/audio behavior
- Synth section supports backend choice (`Simple Synth` / `SoundFont`) and instrument choice (`Piano` / `Guitar`).
- Piano-roll panel is vertically resizable via the main splitter for expanded editing/practice view.
