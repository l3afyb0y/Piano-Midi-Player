#!/usr/bin/env python3
"""Piano Player entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from piano_player.controller import PianoPlayerController


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("PianoPlayer")
    app.setApplicationName("Piano Player")

    controller = PianoPlayerController()
    controller.start()

    result = app.exec()

    controller.stop()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
