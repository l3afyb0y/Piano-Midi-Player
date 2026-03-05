# Third-Party Licensing Notes

This project source code is licensed under `MIT` (see `LICENSE`).

Bundled default instrument packs include:
- `SalamanderGrandPiano-V3+20200602.sfz` (FreePats) under `CC-BY-3.0`
- `EGuitarFSBS-bridge-clean-20220911.sfz` (FreePats) under `CC0-1.0`

The package/install flows include upstream attribution/license readmes under
package documentation paths (including CC0 text for the guitar pack).

Runtime dependencies are installed from system packages and are **not**
relicensed by this project. Notable optional audio dependencies:
- `fluidsynth` (`LGPL-2.1-or-later`)
- `python-pyfluidsynth` (`LGPL-2.1-only`)
- `sfizz` / `sfizz-lib` (`BSD-2-Clause`)

If this project later vendors third-party code (for example `sfizz`), keep that
code under its upstream license and include the full license text in-tree.
