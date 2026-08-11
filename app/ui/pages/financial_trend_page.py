"""Financial Trend page — basic ratios/growth rates (PROJECT_SPEC.md §12)."""
from __future__ import annotations

from PySide6.QtCore import Qt
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

from app.analysis.metrics_engine import compute_all_metrics
from app.data.loader import list_companies, load_financial_facts, to_year_map

LATEST, PRIOR = 2026, 2025


class FinancialTrendPage(QWidget):
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
            f"{PRIOR}→{LATEST} 계산 가능한 지표만 표시됩니다. 필요한 계정이 없으면 "
            "임의로 추정하지 않고 해당 지표를 생략합니다."
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
        metrics = compute_all_metrics(year_map, LATEST, PRIOR)

        self._table.setRowCount(len(metrics))
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["지표", "값", "단위"])

        for row_idx, metric in enumerate(metrics):
            values = [metric.label, f"{metric.value:,.1f}", metric.unit]
            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)
