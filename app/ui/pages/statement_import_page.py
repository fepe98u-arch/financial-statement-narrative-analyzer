"""재무제표 불러오기 page — Excel/CSV import (PROJECT_SPEC.md section 8, 10, 44).

File is read from the local disk only and never leaves the machine. Raw
account names always go through the Account Normalizer and are shown to
the user for confirmation — nothing gets mapped to a canonical account
silently (section 10).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.account_normalizer import MappingMethod
from app.data.cloud_sync_guard import detect_cloud_sync_marker
from app.data.loader import IMPORTED_CSV
from app.data.statement_import import (
    StatementFormatError,
    group_by_account,
    read_wide_statement,
    save_imported_facts,
)
from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES

EXCLUDE_OPTION = "(제외 - 가져오지 않음)"
HIGH_CONFIDENCE = 90.0


class StatementImportPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._long_df = None
        self._combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)

        cloud_marker = detect_cloud_sync_marker(IMPORTED_CSV.parent)
        if cloud_marker:
            warning = QLabel(
                f"⚠ 이 프로젝트 폴더는 '{cloud_marker}' 동기화 폴더 안에 있는 것으로 보입니다. "
                "불러온 재무자료는 이 컴퓨터의 동기화 폴더에도 함께 저장됩니다. 실제 미공개 자료를 "
                "다루신다면 회사 정보보안 정책을 먼저 확인해 주세요. (자동으로 옮기지 않습니다 — "
                "PROJECT_SPEC.md §44)"
            )
            warning.setWordWrap(True)
            warning.setStyleSheet(
                "color: #7a4a00; background-color: #fff3cd; padding: 8px;"
                " border-radius: 4px; margin-bottom: 8px;"
            )
            layout.addWidget(warning)

        note = QLabel(
            "지원 형식: 첫 번째 열이 계정과목, 나머지 열이 연도(예: 2024, 2025)인 Excel(.xlsx)/CSV 파일. "
            "PDF는 아직 지원하지 않습니다. 파일은 이 컴퓨터에서만 읽으며 외부로 전송되지 않습니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(note)

        company_row = QHBoxLayout()
        company_row.addWidget(QLabel("회사명:"))
        self._company_input = QLineEdit()
        self._company_input.setPlaceholderText("예: 가상제조주식회사")
        company_row.addWidget(self._company_input)
        layout.addLayout(company_row)

        file_row = QHBoxLayout()
        choose_btn = QPushButton("파일 선택...")
        choose_btn.clicked.connect(self._choose_file)
        file_row.addWidget(choose_btn)
        self._file_label = QLabel("선택된 파일 없음")
        file_row.addWidget(self._file_label)
        file_row.addStretch()
        layout.addLayout(file_row)

        mapping_note = QLabel(
            "매핑 결과가 낮은 신뢰도이거나 인식되지 않은 계정은 기본값이 '제외'입니다. "
            "직접 계정을 선택해야 가져와집니다."
        )
        mapping_note.setWordWrap(True)
        mapping_note.setStyleSheet("color: #555; margin: 8px 0 4px 0;")
        layout.addWidget(mapping_note)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["원본 계정명", "연도 수", "매핑 방법", "신뢰도", "가져올 계정"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        import_row = QHBoxLayout()
        self._import_btn = QPushButton("가져오기 확정")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._confirm_import)
        import_row.addWidget(self._import_btn)
        import_row.addStretch()
        layout.addLayout(import_row)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _choose_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "재무제표 파일 선택", "", "Excel/CSV (*.xlsx *.xls *.csv)"
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            self._long_df = read_wide_statement(path)
        except StatementFormatError as exc:
            QMessageBox.warning(self, "불러오기 실패", str(exc))
            self._long_df = None
            self._import_btn.setEnabled(False)
            return

        self._file_label.setText(path.name)
        self._populate_mapping_table()
        self._import_btn.setEnabled(True)
        self._status_label.setText("")

    def _populate_mapping_table(self) -> None:
        self._combos.clear()
        groups = group_by_account(self._long_df)

        self._table.setRowCount(len(groups))
        for row_idx, group in enumerate(groups):
            self._table.setItem(row_idx, 0, QTableWidgetItem(group.raw_account_name))
            self._table.setItem(row_idx, 1, QTableWidgetItem(str(group.year_count)))
            self._table.setItem(row_idx, 2, QTableWidgetItem(group.mapping.mapping_method.value))
            self._table.setItem(row_idx, 3, QTableWidgetItem(f"{group.mapping.mapping_confidence:.1f}"))

            combo = QComboBox()
            combo.addItems([EXCLUDE_OPTION] + list(CANONICAL_ACCOUNT_NAMES.values()))
            confident_match = (
                group.mapping.mapping_method != MappingMethod.UNRESOLVED
                and group.mapping.mapping_confidence >= HIGH_CONFIDENCE
            )
            if confident_match:
                combo.setCurrentText(group.mapping.canonical_account_name)
            self._combos[group.raw_account_name] = combo
            self._table.setCellWidget(row_idx, 4, combo)

    def _confirm_import(self) -> None:
        company = self._company_input.text().strip()
        if not company:
            QMessageBox.warning(self, "회사명 필요", "회사명을 입력해 주세요.")
            return
        if self._long_df is None:
            return

        name_to_code = {name: code for code, name in CANONICAL_ACCOUNT_NAMES.items()}
        account_code_by_raw_name = {}
        for raw_name, combo in self._combos.items():
            selected = combo.currentText()
            if selected != EXCLUDE_OPTION:
                account_code_by_raw_name[raw_name] = name_to_code[selected]

        try:
            save_imported_facts(company, self._long_df, account_code_by_raw_name)
        except StatementFormatError as exc:
            QMessageBox.warning(self, "가져오기 실패", str(exc))
            return

        imported_accounts = len(account_code_by_raw_name)
        self._status_label.setText(
            f"✅ '{company}' — 계정 {imported_accounts}개를 가져왔습니다. "
            "다른 화면(Dashboard 등)의 회사 목록에 반영하려면 프로그램을 한 번 재시작해 주세요."
        )
        self._status_label.setStyleSheet("color: #1b5e20; font-weight: bold;")
