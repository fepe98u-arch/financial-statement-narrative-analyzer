"""Account Mapping page: demos the Account Normalizer (PROJECT_SPEC.md §10).

Ambiguous/unresolved mappings are shown as-is, in red — the app never
silently guesses a final answer for those (section 10).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.account_normalizer import MappingMethod, normalize_many
from app.data.raw_account_samples import RAW_ACCOUNT_NAME_SAMPLES

LOW_CONFIDENCE_COLOR = QColor("#c62828")


class AccountMappingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        note = QLabel(
            "예시 원본 계정명(raw_account_name)을 표준 계정(canonical_account_name)으로 "
            "매핑한 결과입니다. mapping_confidence가 낮거나 UNRESOLVED인 항목은 "
            "자동 확정하지 않고 표시만 합니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(note)

        mappings = normalize_many(RAW_ACCOUNT_NAME_SAMPLES)

        table = QTableWidget(len(mappings), 4)
        table.setHorizontalHeaderLabels(
            ["raw_account_name", "canonical_account_name", "mapping_method", "mapping_confidence"]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row_idx, mapping in enumerate(mappings):
            values = [
                mapping.raw_account_name,
                mapping.canonical_account_name or "-",
                mapping.mapping_method.value,
                f"{mapping.mapping_confidence:.1f}",
            ]
            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if mapping.mapping_method in (MappingMethod.UNRESOLVED,) or mapping.mapping_confidence < 90:
                    item.setForeground(LOW_CONFIDENCE_COLOR)
                table.setItem(row_idx, col_idx, item)

        layout.addWidget(table)
