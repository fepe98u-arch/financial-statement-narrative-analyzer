"""Investigation Questions page (PROJECT_SPEC.md section 19).

These questions are generated entirely from local pattern-engine output and
are never sent anywhere — the page says so explicitly so that's never in
doubt while looking at it.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.analysis.investigation_questions import generate_investigation_questions
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company


def _card(source_label: str, source_type: str, questions: list[str]) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background-color: #fafafa; border-left: 4px solid #2e7d32;"
        " border-radius: 4px; padding: 10px; margin-bottom: 8px; }"
    )
    layout = QVBoxLayout(frame)
    title = QLabel(f"{source_label}  ({source_type})")
    title.setStyleSheet("font-weight: bold;")
    layout.addWidget(title)
    for q in questions:
        q_label = QLabel(f"·  {q}")
        q_label.setWordWrap(True)
        layout.addWidget(q_label)
    return frame


class InvestigationQuestionsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._facts = load_financial_facts()
        self._companies = list_companies(self._facts)

        outer = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("회사:"))
        self._company_combo = QComboBox()
        self._company_combo.addItems(self._companies)
        self._company_combo.currentTextChanged.connect(self._render)
        header.addWidget(self._company_combo)
        header.addStretch()
        outer.addLayout(header)

        warning = QLabel(
            "\U0001f512 이 질문은 내부 재무 Pattern에서 로컬로 생성되며, 외부로 전송되지 않습니다."
        )
        warning.setStyleSheet(
            "color: white; background-color: #1b5e20; padding: 6px 10px;"
            " border-radius: 4px; font-weight: bold; margin-bottom: 8px;"
        )
        outer.addWidget(warning)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        scroll.setWidget(self._content)
        outer.addWidget(scroll)

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

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render(self, company: str) -> None:
        self._clear_content()
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

        if not question_sets:
            self._content_layout.addWidget(QLabel("생성된 조사 질문이 없습니다."))

        for qs in question_sets:
            self._content_layout.addWidget(_card(qs.source_label, qs.source_type, qs.questions))

        self._content_layout.addStretch()
