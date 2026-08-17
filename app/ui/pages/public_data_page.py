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

import html
import json
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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
from app.analysis.investigation_questions import generate_investigation_questions, topic_keywords_for
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.config import get_local_ai_model_path, load_settings, save_settings
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company
from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.fake_provider import FakeDartProvider, FakeNewsProvider
from app.public_data_collector.news_provider import MissingCredentialError, NaverNewsProvider, coverage_message
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
        self._table.setMaximumHeight(240)
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
        layout.addStretch()

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
        today = date.today()
        request = PublicCollectionRequest(
            public_company_name=company,
            date_from=date(today.year, 1, 1).isoformat(),
            date_to=today.isoformat(),
            page=1,
            page_size=100,
        )

        self._real_status_label.setText(
            "🌐 PUBLIC DATA COLLECTION: ACTIVE — 최대 10페이지(최대 1,000건)까지 조회 중, 시간이 몇 초 걸릴 수 있습니다..."
        )
        self._real_fetch_btn.setEnabled(False)
        self._clear_real_results()
        QApplication.processEvents()  # paint the "조회 중" status before the blocking multi-page fetch
        try:
            results = NaverNewsProvider().fetch_many(request)
        except MissingCredentialError as exc:
            self._real_status_label.setText(f"🔴 {exc}")
            return
        except Exception as exc:  # network/API errors — surface plainly
            self._real_status_label.setText(f"🔴 조회 실패: {exc}")
            return
        finally:
            self._real_fetch_btn.setEnabled(True)

        coverage = coverage_message(results, request.date_from)
        self._real_status_label.setText(
            f"🌐 PUBLIC DATA COLLECTION: IDLE — 실제 기사 {len(results)}건 수집 완료(중복 제거 후, 회사명만 전송됨). "
            "아래에는 이 중 조사 질문과 관련도 높은 기사만 표시됩니다.\n" + coverage
        )

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
            note = QLabel("이 회사는 연도가 2개 미만이라 조사 질문을 생성할 수 없습니다.")
            note.setStyleSheet("color: #777; margin-top: 8px;")
            self._real_results_layout.addWidget(note)
            return

        latest, prior = years[-1], years[-2]
        year_map = to_year_map(self._facts, company)
        narrative_hits = detect_narrative_patterns(year_map, latest, prior)
        rule_hits = detect_relationship_rules(year_map, latest, prior)
        question_sets = generate_investigation_questions(narrative_hits, rule_hits)
        if not question_sets:
            note = QLabel(
                "이 회사에서 현재 탐지된 Attention Pattern이 없어 조사 질문이 생성되지 않았습니다 "
                "(Attention Patterns 화면에서 직접 확인해 보세요 — 가져온 계정 수가 적으면 "
                "패턴이 안 잡힐 수 있습니다)."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #777; margin-top: 8px;")
            self._real_results_layout.addWidget(note)
            return

        documents = documents_from_provider_results(results)

        # Each article is shown under only the first pattern it matches —
        # without this, the same article (especially one whose topic
        # keywords overlap across two patterns, e.g. "지분법") could appear
        # under every pattern it happens to pass the keyword gate for,
        # which defeats the point of separating them by pattern at all.
        claimed_document_ids: set[str] = set()
        for qs in question_sets[:2]:  # keep the page readable — top 2 pattern sources
            question = qs.questions[0]
            header = QLabel(f"Investigation Question: {question}  (로컬 임베딩으로만 판단, 외부 전송 없음)")
            header.setWordWrap(True)
            header.setStyleSheet(
                "font-weight: bold; background-color: #eeeeee; padding: 6px; border-radius: 4px; margin-top: 12px;"
            )
            self._real_results_layout.addWidget(header)

            keywords = topic_keywords_for(qs.source_type, qs.source_id)
            unclaimed_documents = [d for d in documents if d.public_document_id not in claimed_document_ids]
            matches = rank_public_evidence(model, question, unclaimed_documents, top_k=3, topic_keywords=keywords)
            if not matches:
                empty = QLabel("관련도 높은 기사를 찾지 못했습니다.")
                empty.setStyleSheet("color: #777;")
                self._real_results_layout.addWidget(empty)
                continue

            for match in matches:
                claimed_document_ids.add(match.document_id)
                card = QFrame()
                card.setStyleSheet("QFrame { border-left: 4px solid #1565c0; padding: 8px; margin: 4px 0; }")
                card_layout = QVBoxLayout(card)
                title_text = html.escape(
                    f"[{match.classification.value}] {match.title}  (유사도 {match.similarity:.3f})"
                )
                if match.url:
                    title_text = f'<a href="{html.escape(match.url)}">{title_text}</a>'
                title = QLabel(title_text)
                title.setStyleSheet("font-weight: bold;")
                title.setWordWrap(True)
                title.setOpenExternalLinks(True)
                card_layout.addWidget(title)
                snippet = QLabel(match.chunk.text)
                snippet.setWordWrap(True)
                card_layout.addWidget(snippet)
                self._real_results_layout.addWidget(card)
