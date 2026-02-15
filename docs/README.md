# Documentation

## Build and distribution
- `docs/BUILD.md`: PyInstaller build steps and launcher setup.

## Packaging and install
- `PKGBUILD`: Arch/AUR source package definition.
- `dev/PKGBUILD`: local development package definition (build from current working tree).
- `.SRCINFO`: generated metadata for AUR uploads.
- `piano-player.desktop`: launcher metadata installed by package.
- `scripts/install_arch.sh`: convenience wrapper around `makepkg -si` (`--dev` uses `dev/PKGBUILD`).
- `scripts/install_linux.sh`: Generic Linux installer.
- `scripts/install.sh`: Compatibility wrapper.
- `scripts/download_default_soundfonts.sh`: fetches default CC0 piano and clean electric guitar SoundFonts.

## Current UI/audio behavior
- Synth section supports backend choice (`Simple Synth` / `SoundFont`) and instrument choice (`Piano` / `Guitar`).
- Piano-roll panel is vertically resizable via the main splitter for expanded editing/practice view.
