"""Financial Trend page — basic ratios/growth rates (PROJECT_SPEC.md §12)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.metrics_engine import compute_all_metrics
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company
from app.data.statement_import import load_raw_statement
from app.ui.widgets.statement_sections_view import StatementSectionsView


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

        self._note = QLabel()
        self._note.setStyleSheet("color: #555; margin: 4px 0 8px 0;")
        layout.addWidget(self._note)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setMaximumHeight(260)
        layout.addWidget(self._table)

        self._raw_growth_label = QLabel("계정별 증감율 (원본 재무제표 전체 계정)")
        self._raw_growth_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 16px;")
        layout.addWidget(self._raw_growth_label)

        raw_scroll = QScrollArea()
        raw_scroll.setWidgetResizable(True)
        self._raw_growth_view = StatementSectionsView()
        raw_scroll.setWidget(self._raw_growth_view)
        layout.addWidget(raw_scroll, stretch=1)

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
            self._note.setText("이 회사는 연도가 2개 미만이라 증감률/비율을 계산할 수 없습니다.")
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            self._raw_growth_view.set_empty_message("이 회사는 연도가 2개 미만이라 계정별 증감율을 계산할 수 없습니다.")
            return

        latest, prior = years[-1], years[-2]
        self._note.setText(
            f"{prior}→{latest} 계산 가능한 지표만 표시됩니다. 필요한 계정이 없으면 "
            "임의로 추정하지 않고 해당 지표를 생략합니다."
        )

        year_map = to_year_map(self._facts, company)
        metrics = compute_all_metrics(year_map, latest, prior)

        self._table.setRowCount(len(metrics))
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["지표", "값", "단위"])

        for row_idx, metric in enumerate(metrics):
            values = [metric.label, f"{metric.value:,.1f}", metric.unit]
            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)

        raw_long_df = load_raw_statement(company)
        if raw_long_df is None:
            self._raw_growth_view.set_empty_message(
                "이 회사는 '재무제표 불러오기'로 가져온 원본 데이터가 없어 전체 계정별 증감율을 "
                "계산할 수 없습니다 (가상 데이터 회사이거나, 요약 계정만 별도로 입력된 회사일 수 있습니다)."
            )
        else:
            self._raw_growth_view.set_data(raw_long_df, show_growth=True)
