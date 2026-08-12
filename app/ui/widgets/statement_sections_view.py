"""Reusable read-only view of long-format financial data, split into one
table per statement section (재무상태표/손익계산서/현금흐름표/...) — used
by both the import page's raw preview and the Dashboard's full-statement
view, so the two never drift apart."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.data.statement_import import build_raw_preview_tables


class StatementSectionsView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_empty_message(self, message: str) -> None:
        self.clear()
        label = QLabel(message)
        label.setStyleSheet("color: #777;")
        self._layout.addWidget(label)

    def set_data(self, long_df) -> None:
        self.clear()
        if long_df is None or long_df.height == 0:
            self.set_empty_message("표시할 데이터가 없습니다.")
            return

        for section_label, wide, years in build_raw_preview_tables(long_df):
            header = QLabel(section_label)
            header.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self._layout.addWidget(header)

            table = QTableWidget()
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setMinimumHeight(min(260, 32 * (wide.height + 1)))

            columns = ["raw_account_name"] + [str(y) for y in years]
            headers = ["계정명"] + [str(y) for y in years]
            table.setRowCount(wide.height)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(headers)

            for row_idx, row in enumerate(wide.iter_rows(named=True)):
                for col_idx, col in enumerate(columns):
                    value = row[col]
                    if col == "raw_account_name":
                        text = str(value)
                    elif value is None:
                        text = "-"
                    else:
                        text = f"{value:,.0f}"
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                        if col == "raw_account_name"
                        else Qt.AlignmentFlag.AlignCenter
                    )
                    table.setItem(row_idx, col_idx, item)

            self._layout.addWidget(table)
