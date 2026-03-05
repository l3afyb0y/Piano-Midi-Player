# Documentation

## Build and distribution
- `docs/BUILD.md`: PyInstaller build steps and launcher setup.
- `docs/UI_REFACTOR.md`: rationale and architecture notes for the DAW/Synthesia-inspired UI overhaul.

## Packaging and install
- `PKGBUILD`: Arch/AUR source package definition.
- `dev/PKGBUILD`: local development package definition (build from current working tree).
- `.SRCINFO`: generated metadata for AUR uploads.
- `piano-player.desktop`: launcher metadata installed by package.
- `scripts/install_arch.sh`: convenience wrapper around `makepkg -si` (`--dev` uses `dev/PKGBUILD`).
- `scripts/install_linux.sh`: Generic Linux installer (can auto-install `fluidsynth`/`sfizz` system deps).
- `scripts/install.sh`: Compatibility wrapper.
- `scripts/download_default_soundfonts.sh`: fetches default high-quality SFZ packs (Salamander acoustic grand piano + FSBS clean electric guitar).

## Current UI/audio behavior
- UI uses a menu-first workflow: `File`, `Synth`, `Metronome`, `Settings`, `View`.
- `File` centralizes open/save/import actions; synth/metronome/config controls are moved out of the main surface.
- Synth mode supports explicit backend choice (`Simple Synth` / `SF2 (FluidSynth)` / `SFZ (sfizz)`) and instrument choice (`Acoustic Grand Piano` / `Clean Electric Guitar`).
- Instrument file picker and dropdown are mode-aware: SF2 mode shows/loads `.sf2`, SFZ mode shows/loads `.sfz`.
- Piano-roll panel is vertically resizable via the main splitter for expanded editing/practice view.
- UI includes persistent workspace presets (`Balanced`, `Practice Focus`, `Library Focus`) and MIDI library text filtering.
- UI adds piano-roll view zoom controls and transport micro-polish for faster scanning.
- Keyboard shortcuts: `Space` play/stop, `R` record toggle, `M` metronome toggle, `Ctrl+O` open MIDI, `Ctrl+S` save MIDI.
