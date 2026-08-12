"""Dashboard page (PROJECT_SPEC.md section 46)."""
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

from app.data.loader import build_dashboard_table, list_companies, load_financial_facts
from app.data.statement_import import load_raw_statement
from app.ui.widgets.statement_sections_view import StatementSectionsView

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

        self._raw_section_label = QLabel("전체 재무제표 원본")
        self._raw_section_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 16px;")
        layout.addWidget(self._raw_section_label)

        raw_scroll = QScrollArea()
        raw_scroll.setWidgetResizable(True)
        self._raw_statement_view = StatementSectionsView()
        raw_scroll.setWidget(self._raw_statement_view)
        layout.addWidget(raw_scroll, stretch=1)

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

        raw_long_df = load_raw_statement(company)
        if raw_long_df is None:
            self._raw_statement_view.set_empty_message(
                "이 회사는 '재무제표 불러오기'로 가져온 원본 데이터가 없습니다 "
                "(가상 데이터 회사이거나, 요약 계정만 별도로 입력된 회사일 수 있습니다)."
            )
        else:
            self._raw_statement_view.set_data(raw_long_df)
