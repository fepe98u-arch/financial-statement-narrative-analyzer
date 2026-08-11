"""Stand-in for sidebar sections not built yet, so the navigation shell in
PROJECT_SPEC.md section 45 exists from Phase 1 on, even before every page
has real content."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, phase_note: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch()

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        note_label = QLabel(phase_note)
        note_label.setStyleSheet("color: #777;")
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note_label)

        layout.addStretch()
