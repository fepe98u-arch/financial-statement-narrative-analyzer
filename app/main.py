"""Entry point for the Financial Statement Narrative Analyzer desktop app.

Phase 1: local-only shell + synthetic dashboard. No network code exists
anywhere in this project yet — see PROJECT_SPEC.md section 57 for the phase
plan and section 59 for why nothing here calls out to the internet.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
