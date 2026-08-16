"""Evidence Analysis page (PROJECT_SPEC.md sections 27-31, 42).

Degrades exactly per section 41-42: if no local model is configured (or
sentence-transformers isn't installed), the page shows the required
"Local AI model is not installed." message and lets the user browse to a
local model folder — it never tries to download one itself.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.analysis.embedding_engine import LocalModelNotInstalledError, load_model
from app.analysis.evidence_ranking import (
    EvidenceClassification,
    documents_from_provider_results,
    rank_public_evidence,
)
from app.analysis.investigation_questions import generate_investigation_questions
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.config import get_local_ai_model_path, load_settings, save_settings, set_local_ai_model_path
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company
from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.news_provider import MissingCredentialError, NaverNewsProvider
from app.public_data_collector.schemas import PublicCollectionRequest

CLASSIFICATION_COLORS = {
    EvidenceClassification.POSSIBLE: "#1565c0",
    EvidenceClassification.NO_EVIDENCE_FOUND: "#757575",
}

CONSENT_TEXT = (
    "공개자료 수집 기능은 인터넷을 사용합니다.\n\n"
    "외부 서비스에는 공개 회사 식별정보와 조회기간 등 최소한의 정보만 전달합니다.\n\n"
    "미공개 재무제표, 재무수치, 내부 분석결과, Investigation Question은 외부로 전송되지 않습니다.\n\n"
    "계속하시겠습니까?"
)


class EvidenceAnalysisPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._facts = load_financial_facts()
        self._companies = list_companies(self._facts)
        self._model = None
        self._real_documents_by_company: dict[str, list] = {}

        outer = QVBoxLayout(self)

        model_row = QHBoxLayout()
        self._model_status = QLabel()
        model_row.addWidget(self._model_status)
        choose_btn = QPushButton("모델 폴더 선택...")
        choose_btn.clicked.connect(self._choose_model_folder)
        model_row.addWidget(choose_btn)
        model_row.addStretch()
        outer.addLayout(model_row)

        header = QHBoxLayout()
        header.addWidget(QLabel("회사:"))
        self._company_combo = QComboBox()
        self._company_combo.addItems(self._companies)
        self._company_combo.currentTextChanged.connect(self._render)
        header.addWidget(self._company_combo)
        header.addStretch()
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        scroll.setWidget(self._content)
        outer.addWidget(scroll)

        self._load_model_if_configured()
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

    def _load_model_if_configured(self) -> None:
        path = get_local_ai_model_path()
        try:
            self._model = load_model(path) if path else None
            if self._model is not None:
                self._model_status.setText(f"\U0001f7e2 Local AI model loaded ({path})")
                self._model_status.setStyleSheet("color: #1b5e20; font-weight: bold;")
                return
        except LocalModelNotInstalledError:
            self._model = None

        self._model_status.setText("\U0001f534 Local AI model is not installed.")
        self._model_status.setStyleSheet("color: #b71c1c; font-weight: bold;")

    def _choose_model_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Local Embedding Model 폴더 선택")
        if not folder:
            return
        set_local_ai_model_path(folder)
        self._load_model_if_configured()
        self._render(self._company_combo.currentText())

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _ask_consent(self) -> bool:
        # Same consent flag as the Public Data page — one confirmation
        # covers every real network fetch in the app, not per-page.
        if load_settings().get("public_data_consent_given"):
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

    def _fetch_real_documents(self, company: str) -> None:
        if not self._ask_consent():
            return
        request = PublicCollectionRequest(
            public_company_name=company, date_from="2025-01-01", date_to="2026-08-11", page=1, page_size=20
        )
        try:
            results = NaverNewsProvider().fetch(request)
        except MissingCredentialError as exc:
            QMessageBox.warning(self, "네이버 API 키 필요", str(exc))
            return
        except Exception as exc:  # network/API errors — surface plainly
            QMessageBox.warning(self, "조회 실패", str(exc))
            return

        self._real_documents_by_company[company] = documents_from_provider_results(results)
        self._render(company)

    def _render(self, company: str) -> None:
        self._clear_content()

        if self._model is None:
            self._content_layout.addWidget(
                QLabel(
                    "Local AI 모델이 없어 Semantic Search/Evidence Ranking을 사용할 수 없습니다.\n"
                    "위의 '모델 폴더 선택'으로 로컬에 준비된 sentence-transformers 모델 폴더를 지정하세요.\n"
                    "(모델은 자동으로 다운로드되지 않습니다 — PROJECT_SPEC.md 섹션 42)"
                )
            )
            self._content_layout.addStretch()
            return

        years = years_for_company(self._facts, company)
        if len(years) < 2:
            self._content_layout.addWidget(QLabel("이 회사는 연도가 2개 미만이라 조사 질문을 생성할 수 없습니다."))
            self._content_layout.addStretch()
            return

        latest, prior = years[-1], years[-2]
        year_map = to_year_map(self._facts, company)
        narrative_hits = detect_narrative_patterns(year_map, latest, prior)
        rule_hits = detect_relationship_rules(year_map, latest, prior)
        question_sets = generate_investigation_questions(narrative_hits, rule_hits)

        # Synthetic companies (ABC Manufacturing, Sample Electronics) get
        # the local fake-article fixture, no network involved. Anything
        # else (an imported real company) has no such fixture — offer a
        # real fetch instead of just reporting nothing's there.
        documents = documents_for_company(company) or self._real_documents_by_company.get(company, [])

        if not question_sets:
            self._content_layout.addWidget(QLabel("현재 조사 질문이 없어 매칭할 대상이 없습니다."))
        if not documents:
            note = QLabel(
                "이 회사에 대한 가상 공개자료 예시가 없습니다 (합성 회사 전용). "
                "실제 네이버 뉴스를 가져와서 분석하시겠습니까?"
            )
            note.setWordWrap(True)
            self._content_layout.addWidget(note)

            fetch_btn = QPushButton("🌐 실제 네이버 뉴스 가져오기")
            fetch_btn.clicked.connect(lambda: self._fetch_real_documents(company))
            self._content_layout.addWidget(fetch_btn)
            self._content_layout.addStretch()
            return

        for qs in question_sets[:2]:  # keep the page readable — top 2 pattern sources
            for question in qs.questions[:1]:  # one representative question per source
                self._content_layout.addWidget(self._question_header(question))
                matches = rank_public_evidence(self._model, question, documents, top_k=3)
                for match in matches:
                    self._content_layout.addWidget(self._evidence_card(match))

        self._content_layout.addStretch()

    def _question_header(self, question: str) -> QLabel:
        label = QLabel(f"Investigation Question: {question}")
        label.setStyleSheet(
            "font-weight: bold; background-color: #eeeeee; padding: 6px;"
            " border-radius: 4px; margin-top: 10px;"
        )
        label.setWordWrap(True)
        return label

    def _evidence_card(self, match) -> QFrame:
        frame = QFrame()
        accent = CLASSIFICATION_COLORS.get(match.classification, "#757575")
        frame.setStyleSheet(
            f"QFrame {{ border-left: 4px solid {accent}; padding: 8px; margin: 4px 0; }}"
        )
        layout = QVBoxLayout(frame)
        title = QLabel(f"[{match.classification.value}] {match.title}  (유사도 {match.similarity:.3f})")
        title.setStyleSheet("font-weight: bold;")
        title.setWordWrap(True)
        layout.addWidget(title)
        meta = QLabel(f"{match.source} · {match.published_at}")
        meta.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(meta)
        snippet = QLabel(match.chunk.text)
        snippet.setWordWrap(True)
        layout.addWidget(snippet)
        return frame
