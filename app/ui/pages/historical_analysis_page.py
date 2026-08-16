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
from app.data.loader import (
    account_name_map,
    list_companies,
    load_financial_facts,
    to_year_map,
    years_for_company,
)

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

        self._note = QLabel()
        self._note.setStyleSheet("color: #555; margin: 4px 0 8px 0;")
        layout.addWidget(self._note)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        self._render(self._companies[0])

    def refresh(self) -> None:
        """Called when this page becomes visible again — picks up companies
        imported since the page was first built, without an app restart."""
        self._facts = load_financial_facts()
        new_companies = list_companies(self._facts)
        if new_companies == self._companies:
            return
        current = self._company_combo.currentText()
        self._companies = new_companies
        self._company_combo.blockSignals(True)
        self._company_combo.clear()
        self._company_combo.addItems(self._companies)
        target = current if current in self._companies else self._companies[0]
        self._company_combo.setCurrentText(target)
        self._company_combo.blockSignals(False)
        self._render(target)

    def _render(self, company: str) -> None:
        years = years_for_company(self._facts, company)
        if len(years) < 2:
            self._note.setText("이 회사는 연도가 2개 미만이라 과거 패턴과 비교할 수 없습니다.")
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return

        self._note.setText(f"당기({years[-1]}) YoY를 {years[0]}~{years[-2]} 각 연도 자체 변동과 비교해 분류합니다.")

        year_map = to_year_map(self._facts, company)
        names = account_name_map(self._facts, company)
        results = classify_all_accounts(year_map, names, years)
        results.sort(key=lambda r: abs(r.current_growth), reverse=True)

        history_years = years[1:-1]
        columns = ["account"] + [f"{y} YoY" for y in history_years] + [f"{years[-1]} YoY (당기)", "분류"]

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
