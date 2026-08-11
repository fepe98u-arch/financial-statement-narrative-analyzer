"""Historical Analysis page (PROJECT_SPEC.md sections 17-18)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.historical_patterns import HistoricalClassification, classify_all_accounts
from app.data.loader import account_name_map, list_companies, load_financial_facts, to_year_map

YEARS = [2022, 2023, 2024, 2025, 2026]

CLASSIFICATION_COLORS = {
    HistoricalClassification.INTENSIFIED_PATTERN: QColor("#c62828"),
    HistoricalClassification.NEW_PATTERN: QColor("#ef6c00"),
    HistoricalClassification.RECURRING_PATTERN: QColor("#1565c0"),
    HistoricalClassification.REVERSAL_PATTERN: QColor("#6a1b9a"),
    HistoricalClassification.NORMAL_RANGE: QColor("#616161"),
}


class HistoricalAnalysisPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._facts = load_financial_facts()
        self._companies = list_companies(self._facts)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("회사:"))
        self._company_combo = QComboBox()
        self._company_combo.addItems(self._companies)
        self._company_combo.currentTextChanged.connect(self._render)
        header.addWidget(self._company_combo)
        header.addStretch()
        layout.addLayout(header)

        note = QLabel(
            f"당기({YEARS[-1]}) YoY를 {YEARS[1]}~{YEARS[-2]} 각 연도 자체 변동과 비교해 분류합니다."
        )
        note.setStyleSheet("color: #555; margin: 4px 0 8px 0;")
        layout.addWidget(note)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        self._render(self._companies[0])

    def _render(self, company: str) -> None:
        year_map = to_year_map(self._facts, company)
        names = account_name_map(self._facts, company)
        results = classify_all_accounts(year_map, names, YEARS)
        results.sort(key=lambda r: abs(r.current_growth), reverse=True)

        history_years = YEARS[1:-1]
        columns = ["account"] + [f"{y} YoY" for y in history_years] + [f"{YEARS[-1]} YoY (당기)", "분류"]

        self._table.setRowCount(len(results))
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)

        for row_idx, r in enumerate(results):
            cells = [r.account_name]
            for y in history_years:
                g = r.historical_growths.get(y)
                cells.append("-" if g is None else f"{g:+.1f}%")
            cells.append(f"{r.current_growth:+.1f}%")
            cells.append(r.classification.value)

            for col_idx, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == len(cells) - 1:
                    item.setForeground(CLASSIFICATION_COLORS.get(r.classification, QColor("black")))
                self._table.setItem(row_idx, col_idx, item)
