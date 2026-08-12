"""재무제표 불러오기 page — Excel/CSV import + direct DART import
(PROJECT_SPEC.md sections 8, 10, 24, 44).

Files are read from local disk only. DART fetches send only
corp_code/bsns_year/reprt_code/fs_div (section 2's "technical parameters a
public API needs") — never anything derived from this app's own analysis.
Both paths funnel into the same account-mapping preview: raw account names
always go through the Account Normalizer and require explicit confirmation
for anything low-confidence or unrecognized (section 10).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
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
    rows_to_long_df,
    save_imported_facts,
)
from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES
from app.public_data_collector.dart_financials import (
    MissingCredentialError,
    fetch_financial_statement_rows,
    search_corp_codes,
)

EXCLUDE_OPTION = "(제외 - 가져오지 않음)"

# Only EXACT/ACCOUNT_DICTIONARY matches get pre-selected. FUZZY matches are
# never auto-accepted regardless of score — real DART line items showed
# WRatio scoring pure-substring pairs like "장기차입금의 상환" (a cash-flow
# movement) against "장기차입금" (a balance-sheet balance) at the same
# confidence as genuine synonyms, which would silently merge unrelated
# concepts. Always require a human to actively pick a FUZZY suggestion.
AUTO_ACCEPT_METHODS = (MappingMethod.EXACT, MappingMethod.ACCOUNT_DICTIONARY)


class StatementImportPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._long_df = None
        self._combos: dict[str, QComboBox] = {}
        self._corp_matches: list[dict] = []

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

        company_row = QHBoxLayout()
        company_row.addWidget(QLabel("회사명:"))
        self._company_input = QLineEdit()
        self._company_input.setPlaceholderText("예: 가상제조주식회사")
        company_row.addWidget(self._company_input)
        layout.addLayout(company_row)

        tabs = QTabWidget()
        tabs.addTab(self._build_file_tab(), "파일에서 가져오기")
        tabs.addTab(self._build_dart_tab(), "DART API에서 가져오기")
        layout.addWidget(tabs)

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

    # ---- 파일 tab ----------------------------------------------------

    def _build_file_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        note = QLabel(
            "지원 형식: 첫 번째 열이 계정과목, 나머지 열이 연도(예: 2024, 2025)인 Excel(.xlsx)/CSV 파일. "
            "PDF는 아직 지원하지 않습니다. 파일은 이 컴퓨터에서만 읽으며 외부로 전송되지 않습니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(note)

        file_row = QHBoxLayout()
        choose_btn = QPushButton("파일 선택...")
        choose_btn.clicked.connect(self._choose_file)
        file_row.addWidget(choose_btn)
        self._file_label = QLabel("선택된 파일 없음")
        file_row.addWidget(self._file_label)
        file_row.addStretch()
        layout.addLayout(file_row)
        layout.addStretch()
        return tab

    def _choose_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "재무제표 파일 선택", "", "Excel/CSV (*.xlsx *.xls *.csv)"
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            long_df = read_wide_statement(path)
        except StatementFormatError as exc:
            QMessageBox.warning(self, "불러오기 실패", str(exc))
            return

        self._file_label.setText(path.name)
        self._long_df = long_df
        self._populate_mapping_table()
        self._import_btn.setEnabled(True)
        self._status_label.setText("")

    # ---- DART API tab --------------------------------------------------

    def _build_dart_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        note = QLabel(
            "DART에 공개 제출된 재무제표를 직접 가져옵니다. 이 회사의 corp_code/조회연도 등 "
            "기술 파라미터만 DART로 전송되며, 이 프로그램의 분석 결과는 전송되지 않습니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(note)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("회사 검색:"))
        self._corp_search_input = QLineEdit()
        self._corp_search_input.setPlaceholderText("예: 삼성전자")
        self._corp_search_input.returnPressed.connect(self._search_corp_codes)
        search_row.addWidget(self._corp_search_input)
        search_btn = QPushButton("검색")
        search_btn.clicked.connect(self._search_corp_codes)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self._corp_list = QListWidget()
        self._corp_list.setMaximumHeight(120)
        self._corp_list.itemSelectionChanged.connect(self._on_corp_selected)
        layout.addWidget(self._corp_list)

        options_row = QHBoxLayout()
        last_completed_year = dt.date.today().year - 1

        options_row.addWidget(QLabel("최근연도:"))
        self._latest_year_spin = QSpinBox()
        self._latest_year_spin.setRange(2015, dt.date.today().year)
        self._latest_year_spin.setValue(last_completed_year)
        options_row.addWidget(self._latest_year_spin)

        options_row.addWidget(QLabel("연도 수:"))
        self._num_years_spin = QSpinBox()
        self._num_years_spin.setRange(2, 10)
        self._num_years_spin.setValue(5)
        options_row.addWidget(self._num_years_spin)

        options_row.addWidget(QLabel("구분:"))
        self._fs_div_combo = QComboBox()
        self._fs_div_combo.addItems(["연결(CFS)", "별도(OFS)"])
        options_row.addWidget(self._fs_div_combo)
        options_row.addStretch()
        layout.addLayout(options_row)

        fetch_row = QHBoxLayout()
        self._dart_fetch_btn = QPushButton("DART에서 조회")
        self._dart_fetch_btn.clicked.connect(self._fetch_from_dart)
        fetch_row.addWidget(self._dart_fetch_btn)
        fetch_row.addStretch()
        layout.addLayout(fetch_row)

        self._dart_status_label = QLabel()
        self._dart_status_label.setWordWrap(True)
        layout.addWidget(self._dart_status_label)
        layout.addStretch()
        return tab

    def _search_corp_codes(self) -> None:
        query = self._corp_search_input.text().strip()
        if not query:
            return
        try:
            self._corp_matches = search_corp_codes(query)
        except MissingCredentialError as exc:
            QMessageBox.warning(self, "DART 키 필요", str(exc))
            return

        self._corp_list.clear()
        for corp in self._corp_matches:
            self._corp_list.addItem(f"{corp['corp_name']}  (종목코드: {corp['stock_code']})")

        if not self._corp_matches:
            self._dart_status_label.setText("검색 결과가 없습니다 (상장회사만 검색됩니다).")

    def _on_corp_selected(self) -> None:
        row = self._corp_list.currentRow()
        if 0 <= row < len(self._corp_matches):
            self._company_input.setText(self._corp_matches[row]["corp_name"])

    def _fetch_from_dart(self) -> None:
        row = self._corp_list.currentRow()
        if not (0 <= row < len(self._corp_matches)):
            QMessageBox.warning(self, "회사 선택 필요", "먼저 회사를 검색하고 목록에서 선택해 주세요.")
            return

        corp = self._corp_matches[row]
        fs_div = "CFS" if self._fs_div_combo.currentIndex() == 0 else "OFS"

        self._dart_status_label.setText("DART에서 조회 중...")
        self._dart_fetch_btn.setEnabled(False)
        try:
            rows = fetch_financial_statement_rows(
                corp["corp_code"],
                latest_year=self._latest_year_spin.value(),
                num_years=self._num_years_spin.value(),
                fs_div=fs_div,
            )
            long_df = rows_to_long_df(rows)
        except MissingCredentialError as exc:
            QMessageBox.warning(self, "DART 키 필요", str(exc))
            return
        except StatementFormatError as exc:
            QMessageBox.warning(self, "조회 실패", str(exc))
            return
        except Exception as exc:  # network/API errors — surface plainly, never silently succeed
            QMessageBox.warning(self, "DART 조회 실패", str(exc))
            return
        finally:
            self._dart_fetch_btn.setEnabled(True)

        self._long_df = long_df
        self._populate_mapping_table()
        self._import_btn.setEnabled(True)
        self._dart_status_label.setText(f"✅ {corp['corp_name']} — {long_df.height}개 데이터 항목을 불러왔습니다.")
        self._status_label.setText("")

    # ---- shared mapping table + confirm ------------------------------

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
            if group.mapping.mapping_method in AUTO_ACCEPT_METHODS:
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
