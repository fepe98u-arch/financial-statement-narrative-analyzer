"""Entry point for the Financial Statement Narrative Analyzer desktop app.

The only network code in the project lives in app/public_data_collector/
(PROJECT_SPEC.md section 23) and only runs when a user explicitly triggers
a public-data fetch — nothing here auto-connects on startup.
"""
from __future__ import annotations

import sys

from app.env_loader import load_env_file

load_env_file()

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
