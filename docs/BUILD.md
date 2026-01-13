# Build App

This project can be packaged into a standalone app with PyInstaller.

## Install build tools
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Build
```bash
python scripts/build_app.py
```

Output goes to `dist/`:
- Windows: `dist/Piano Player/Piano Player.exe`
- macOS: `dist/Piano Player.app`
- Linux: `dist/Piano Player/Piano Player`

## Programs list
- Windows: create a Start Menu shortcut to the built `.exe` (or wrap it in an installer).
- macOS: move `Piano Player.app` into `/Applications`.
- Linux: run `bash scripts/install_desktop.sh` to install a `.desktop` entry and launcher.
