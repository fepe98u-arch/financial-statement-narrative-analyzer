"""Public Data page.

Three things live here:
1. The Phase 5 synthetic document fixture (read-only preview).
2. A Fake Provider simulation that runs a real PublicCollectionRequest
   through the actual Network Guard and Fake Provider code — no real
   network call.
3. A **real** Naver News fetch — this one actually connects to the
   internet. Only runs when the user clicks the button, and only after a
   first-run consent dialog (PROJECT_SPEC.md section 34-35).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.analysis.document_parsing import chunk_document, parse_document
from app.analysis.embedding_engine import LocalModelNotInstalledError, load_model
from app.analysis.evidence_ranking import documents_from_provider_results, rank_public_evidence
from app.analysis.investigation_questions import generate_investigation_questions
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.config import get_local_ai_model_path, load_settings, save_settings
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company
from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.fake_provider import FakeDartProvider, FakeNewsProvider
from app.public_data_collector.news_provider import MissingCredentialError, NaverNewsProvider
from app.public_data_collector.schemas import PublicCollectionRequest

CONSENT_TEXT = (
    "공개자료 수집 기능은 인터넷을 사용합니다.\n\n"
    "외부 서비스에는 공개 회사 식별정보와 조회기간 등 최소한의 정보만 전달합니다.\n\n"
    "미공개 재무제표, 재무수치, 내부 분석결과, Investigation Question은 외부로 전송되지 않습니다.\n\n"
    "계속하시겠습니까?"
)


class PublicDataPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._companies = list_companies(load_financial_facts())
        self._facts = load_financial_facts()

        layout = QVBoxLayout(self)

        note = QLabel(
            "위 표는 로컬 가상(synthetic) 공개자료 예시입니다.\n"
            "'Fake Provider 시뮬레이션'은 실제 요청 검증 로직을 가상 데이터로 통과시켜 봅니다 — "
            "네트워크 요청이 발생하지 않습니다. 맨 아래 '실제 네이버 뉴스 가져오기'만 진짜로 "
            "인터넷에 연결됩니다."
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

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 14px 0; color: #ddd;")
        layout.addWidget(divider)

        real_note = QLabel(
            "🌐 아래 버튼은 실제로 네이버 뉴스 API에 연결됩니다. 전송되는 값은 회사명뿐이며, "
            "내부 분석 결과나 조사 질문은 절대 검색어로 쓰이지 않습니다."
        )
        real_note.setWordWrap(True)
        real_note.setStyleSheet(
            "color: white; background-color: #b71c1c; padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        layout.addWidget(real_note)

        real_row = QHBoxLayout()
        self._real_fetch_btn = QPushButton("실제 네이버 뉴스 가져오기")
        self._real_fetch_btn.clicked.connect(self._run_real_fetch)
        real_row.addWidget(self._real_fetch_btn)
        real_row.addStretch()
        layout.addLayout(real_row)

        self._real_status_label = QLabel()
        self._real_status_label.setWordWrap(True)
        self._real_status_label.setStyleSheet("margin-top: 6px;")
        layout.addWidget(self._real_status_label)

        self._real_results_container = QWidget()
        self._real_results_layout = QVBoxLayout(self._real_results_container)
        self._real_results_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._real_results_container)

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
        self._real_status_label.setText("")
        self._clear_real_results()

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

    def _has_consent(self) -> bool:
        return bool(load_settings().get("public_data_consent_given"))

    def _ask_consent(self) -> bool:
        if self._has_consent():
            return True
        reply = QMessageBox.question(
            self, "공개자료 수집 안내", CONSENT_TEXT, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            settings = load_settings()
            settings["public_data_consent_given"] = True
            save_settings(settings)
            return True
        return False

    def _clear_real_results(self) -> None:
        while self._real_results_layout.count():
            item = self._real_results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _run_real_fetch(self) -> None:
        if not self._ask_consent():
            return

        company = self._company_combo.currentText()
        request = PublicCollectionRequest(
            public_company_name=company, date_from="2025-01-01", date_to="2026-08-11", page=1, page_size=20
        )

        self._real_status_label.setText("🌐 PUBLIC DATA COLLECTION: ACTIVE — 조회 중...")
        self._real_fetch_btn.setEnabled(False)
        self._clear_real_results()
        try:
            results = NaverNewsProvider().fetch(request)
        except MissingCredentialError as exc:
            self._real_status_label.setText(f"🔴 {exc}")
            return
        except Exception as exc:  # network/API errors — surface plainly
            self._real_status_label.setText(f"🔴 조회 실패: {exc}")
            return
        finally:
            self._real_fetch_btn.setEnabled(True)

        self._real_status_label.setText(
            f"🌐 PUBLIC DATA COLLECTION: IDLE — 실제 기사 {len(results)}건 수집 완료 (회사명만 전송됨)"
        )

        for r in results:
            self._real_results_layout.addWidget(self._article_card(r["title"], r["source"], r["published_at"], r["url"]))

        self._render_relevance_ranking(company, results)

    def _render_relevance_ranking(self, company: str, results: list[dict]) -> None:
        model_path = get_local_ai_model_path()
        try:
            model = load_model(model_path) if model_path else None
        except LocalModelNotInstalledError:
            model = None

        if model is None:
            note = QLabel(
                "Local AI 모델이 없어 조사 질문과의 관련도 분석은 생략합니다. "
                "(Evidence Analysis 화면에서 모델 폴더를 지정하면 여기서도 사용됩니다.)"
            )
            note.setStyleSheet("color: #777; margin-top: 8px;")
            self._real_results_layout.addWidget(note)
            return

        years = years_for_company(self._facts, company)
        if len(years) < 2:
            return
        latest, prior = years[-1], years[-2]
        year_map = to_year_map(self._facts, company)
        narrative_hits = detect_narrative_patterns(year_map, latest, prior)
        rule_hits = detect_relationship_rules(year_map, latest, prior)
        question_sets = generate_investigation_questions(narrative_hits, rule_hits)
        if not question_sets:
            return

        question = question_sets[0].questions[0]
        header = QLabel(f"Investigation Question: {question}  (로컬 임베딩으로만 판단, 외부 전송 없음)")
        header.setWordWrap(True)
        header.setStyleSheet(
            "font-weight: bold; background-color: #eeeeee; padding: 6px; border-radius: 4px; margin-top: 12px;"
        )
        self._real_results_layout.addWidget(header)

        documents = documents_from_provider_results(results)
        for match in rank_public_evidence(model, question, documents, top_k=5):
            card = QFrame()
            card.setStyleSheet("QFrame { border-left: 4px solid #1565c0; padding: 8px; margin: 4px 0; }")
            card_layout = QVBoxLayout(card)
            title = QLabel(f"[{match.classification.value}] {match.title}  (유사도 {match.similarity:.3f})")
            title.setStyleSheet("font-weight: bold;")
            title.setWordWrap(True)
            card_layout.addWidget(title)
            snippet = QLabel(match.chunk.text)
            snippet.setWordWrap(True)
            card_layout.addWidget(snippet)
            self._real_results_layout.addWidget(card)

    def _article_card(self, title: str, source: str, published_at: str, url: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { border-left: 4px solid #2e7d32; padding: 6px; margin: 3px 0; }")
        card_layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(title_label)
        meta = QLabel(f"{source} · {published_at} · {url}")
        meta.setWordWrap(True)
        meta.setStyleSheet("color: #666; font-size: 11px;")
        card_layout.addWidget(meta)
        return frame
