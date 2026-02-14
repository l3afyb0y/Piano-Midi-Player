# Build App

Package Piano Player into a standalone app with PyInstaller.

## Install build tooling
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Build
```bash
python scripts/build_app.py
```

Output is written to `dist/`:
- Linux: `dist/Piano Player/Piano Player`
- Windows: `dist/Piano Player/Piano Player.exe`
- macOS: `dist/Piano Player.app`

## Desktop launcher
After building, install launcher files using:
```bash
bash scripts/install_desktop.sh
```

For system-wide launcher install:
```bash
bash scripts/install_desktop.sh --system
```
