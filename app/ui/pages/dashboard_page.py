"""Dashboard page (PROJECT_SPEC.md section 46)."""
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

from app.data.loader import build_dashboard_table, list_companies, load_financial_facts

ATTENTION_THRESHOLD_PCT = 30.0


class DashboardPage(QWidget):
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

        self._title = QLabel()
        self._title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 8px 0;")
        layout.addWidget(self._title)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        self._note = QLabel(
            f"⚠ 최근연도 YoY {ATTENTION_THRESHOLD_PCT:.0f}% 이상 변동은 Review Pattern 후보로"
            " 표시됩니다 (오류/분식 판단 아님)."
        )
        self._note.setStyleSheet("color: #b71c1c; margin-top: 6px;")
        layout.addWidget(self._note)

        self._render(self._companies[0])

    def _render(self, company: str) -> None:
        table_df, years = build_dashboard_table(self._facts, company)
        year_range = f"{years[0]}" if len(years) == 1 else f"{years[0]}~{years[-1]}"
        self._title.setText(f"{company} — {year_range}")

        columns = ["account_name"] + [str(y) for y in years] + ["yoy_pct"]
        headers = ["계정"] + [str(y) for y in years] + [f"{years[-1]} YoY %"]

        self._table.setRowCount(table_df.height)
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(headers)

        for row_idx, row in enumerate(table_df.iter_rows(named=True)):
            for col_idx, col in enumerate(columns):
                value = row[col]
                if col == "account_name":
                    text = str(value)
                elif value is None:
                    text = "-"
                elif col == "yoy_pct":
                    text = f"{value:+.1f}%"
                else:
                    text = f"{value:,.0f}"

                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == "yoy_pct" and value is not None and abs(value) >= ATTENTION_THRESHOLD_PCT:
                    item.setForeground(Qt.GlobalColor.red)
                self._table.setItem(row_idx, col_idx, item)
