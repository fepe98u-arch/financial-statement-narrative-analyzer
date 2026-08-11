"""Public Data page.

Two things live here: the Phase 5 synthetic document fixture (read-only
preview), and a Phase 7 "Fake Provider" simulation that runs a real
PublicCollectionRequest through the actual Network Guard and Fake Provider
code — so you can see exactly what would leave the machine, without any
real network call existing yet (that's Phase 8-9).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.document_parsing import chunk_document, parse_document
from app.data.loader import list_companies, load_financial_facts
from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.fake_provider import FakeDartProvider, FakeNewsProvider
from app.public_data_collector.schemas import PublicCollectionRequest


class PublicDataPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._companies = list_companies(load_financial_facts())

        layout = QVBoxLayout(self)

        note = QLabel(
            "위 표는 로컬 가상(synthetic) 공개자료 예시입니다.\n"
            "아래 'Fake Provider 시뮬레이션'은 Phase 7에서 만든 실제 요청 검증 로직을 "
            "그대로 통과시켜 봅니다 — 실제 인터넷 연결은 Phase 8(DART)·Phase 9(뉴스)에서 "
            "추가되며, 그 전까지는 네트워크 요청이 전혀 발생하지 않습니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(note)

        header = QHBoxLayout()
        header.addWidget(QLabel("회사:"))
        self._company_combo = QComboBox()
        self._company_combo.addItems(self._companies)
        self._company_combo.currentTextChanged.connect(self._render)
        header.addWidget(self._company_combo)
        header.addStretch()
        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        sim_row = QHBoxLayout()
        sim_btn = QPushButton("Fake Provider 시뮬레이션 실행")
        sim_btn.clicked.connect(self._run_simulation)
        sim_row.addWidget(sim_btn)
        sim_row.addStretch()
        layout.addLayout(sim_row)

        self._sim_output = QLabel()
        self._sim_output.setWordWrap(True)
        self._sim_output.setStyleSheet(
            "font-family: Consolas, monospace; background-color: #f5f5f5; padding: 8px;"
            " border-radius: 4px; margin-top: 6px;"
        )
        layout.addWidget(self._sim_output)

        self._render(self._companies[0])

    def _render(self, company: str) -> None:
        docs = documents_for_company(company)

        columns = ["source", "title", "published_at", "chunks"]
        headers = ["출처", "제목", "게시일", "청크 수"]

        self._table.setRowCount(len(docs))
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(headers)

        for row_idx, doc in enumerate(docs):
            chunk_count = len(chunk_document(parse_document(doc)))
            values = [doc.source, doc.title, doc.published_at, str(chunk_count)]
            for col_idx, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)

        self._sim_output.setText("")

    def _run_simulation(self) -> None:
        company = self._company_combo.currentText()
        request = PublicCollectionRequest(
            public_company_name=company, date_from="2025-01-01", date_to="2026-08-11", page=1, page_size=20
        )

        news = FakeNewsProvider().fetch(request)
        dart = FakeDartProvider().fetch(request)

        outbound_shown = json.dumps(request.to_outbound_payload(), ensure_ascii=False, indent=2)
        self._sim_output.setText(
            "실제로 전송되는(시뮬레이션) 요청 — 허용된 필드만 포함:\n"
            f"{outbound_shown}\n\n"
            f"결과: 뉴스 {len(news)}건, DART {len(dart)}건 (전부 로컬 가상 데이터)"
        )
