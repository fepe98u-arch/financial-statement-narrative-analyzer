"""Financial Trend page — basic ratios/growth rates (PROJECT_SPEC.md §12)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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
from app.data.statement_import import compute_account_growth, load_raw_statement
from app.ui.widgets.statement_sections_view import StatementSectionsView

# Same threshold Dashboard uses to flag a YoY move as a Review Pattern
# candidate (app/ui/pages/dashboard_page.py's ATTENTION_THRESHOLD_PCT) —
# kept as a separate constant here rather than a cross-page import, but the
# value should stay in sync with that one.
NOTABLE_GROWTH_THRESHOLD_PCT = 30.0


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
        layout.addWidget(self._table)

        self._notable_label = QLabel()
        self._notable_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 16px;")
        layout.addWidget(self._notable_label)

        self._notable_note = QLabel(
            f"YoY {NOTABLE_GROWTH_THRESHOLD_PCT:.0f}% 이상 변동한 계정을 전체 원본 재무제표에서 모아 보여줍니다 "
            "(계정 간 인과관계를 추정하지 않고, 변동폭만으로 나열합니다 — 서로 관련이 있는지는 사람이 판단해야 합니다)."
        )
        self._notable_note.setWordWrap(True)
        self._notable_note.setStyleSheet("color: #555; margin-bottom: 6px;")
        layout.addWidget(self._notable_note)

        self._notable_table = QTableWidget()
        self._notable_table.verticalHeader().setVisible(False)
        self._notable_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._notable_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._notable_table)

        self._raw_growth_label = QLabel("계정별 증감율 (원본 재무제표 전체 계정)")
        self._raw_growth_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 16px;")
        layout.addWidget(self._raw_growth_label)

        raw_scroll = QScrollArea()
        raw_scroll.setWidgetResizable(True)
        self._raw_growth_view = StatementSectionsView()
        raw_scroll.setWidget(self._raw_growth_view)
        layout.addWidget(raw_scroll, stretch=1)

        self._render(self._companies[0])

    @staticmethod
    def _fit_table_height(table: QTableWidget, cap: int | None = None) -> None:
        """Sizes the table to exactly fit its current rows — no clipped
        partial row, no dead whitespace below the last row. With many rows
        (the notable-movers table can have dozens), `cap` keeps it from
        growing tall enough to push the rest of the page out of view; the
        table gets its own internal scrollbar past that point instead."""
        table.resizeRowsToContents()
        total = table.horizontalHeader().height() + 2
        for row in range(table.rowCount()):
            total += table.rowHeight(row)
        total = max(total, table.horizontalHeader().height() + 30)
        table.setMaximumHeight(min(total, cap) if cap else total)

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
            self._notable_label.setText("")
            self._notable_table.setRowCount(0)
            self._notable_table.setColumnCount(0)
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
        self._fit_table_height(self._table)

        raw_long_df = load_raw_statement(company)
        if raw_long_df is None:
            self._notable_label.setText("")
            self._notable_table.setRowCount(0)
            self._notable_table.setColumnCount(0)
            self._raw_growth_view.set_empty_message(
                "이 회사는 '재무제표 불러오기'로 가져온 원본 데이터가 없어 전체 계정별 증감율을 "
                "계산할 수 없습니다 (가상 데이터 회사이거나, 요약 계정만 별도로 입력된 회사일 수 있습니다)."
            )
            return

        self._raw_growth_view.set_data(raw_long_df, show_growth=True)

        all_growth = compute_account_growth(raw_long_df)
        notable = sorted(
            (g for g in all_growth if abs(g.growth_pct) >= NOTABLE_GROWTH_THRESHOLD_PCT),
            key=lambda g: abs(g.growth_pct),
            reverse=True,
        )
        self._notable_label.setText(f"⚠ 주목할 만한 계정 변동 ({len(notable)}건)")

        self._notable_table.setRowCount(len(notable))
        self._notable_table.setColumnCount(5)
        self._notable_table.setHorizontalHeaderLabels(["계정명", "구분", f"{prior}", f"{latest}", "증감율"])
        for row_idx, g in enumerate(notable):
            values = [g.raw_account_name, g.section, f"{g.prior_amount:,.0f}", f"{g.latest_amount:,.0f}", f"{g.growth_pct:+.1f}%"]
            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    if col_idx in (0, 1)
                    else Qt.AlignmentFlag.AlignCenter
                )
                if col_idx == 4:
                    item.setForeground(QColor("#c62828") if g.growth_pct < 0 else QColor("#1565c0"))
                self._notable_table.setItem(row_idx, col_idx, item)
        self._fit_table_height(self._notable_table, cap=320)
