"""Attention Patterns page: Relationship Rule Engine + Business Narrative
Pattern Engine output (PROJECT_SPEC.md sections 13-16).

Deliberately avoids words like "오류"/"분식" anywhere in this file — see
section 50 for the vocabulary the program is required to stick to.
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

from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company


def _card(title: str, subtitle: str, body: str, accent: str) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame {{ background-color: #fafafa; border-left: 4px solid {accent};"
        " border-radius: 4px; padding: 10px; margin-bottom: 8px; }}"
    )
    layout = QVBoxLayout(frame)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(subtitle_label)
    body_label = QLabel(body)
    body_label.setWordWrap(True)
    layout.addWidget(body_label)
    return frame


class AttentionPatternsPage(QWidget):
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        outer.addWidget(scroll)

        self._render(self._companies[0])

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
            self._content_layout.addWidget(QLabel("이 회사는 연도가 2개 미만이라 패턴을 계산할 수 없습니다."))
            self._content_layout.addStretch()
            return

        latest, prior = years[-1], years[-2]
        year_map = to_year_map(self._facts, company)

        narrative_hits = detect_narrative_patterns(year_map, latest, prior)
        section = QLabel(f"Business Narrative Pattern ({len(narrative_hits)}건)")
        section.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 6px;")
        self._content_layout.addWidget(section)

        if not narrative_hits:
            self._content_layout.addWidget(QLabel("주목할 만한 Cross-Account Cluster가 발견되지 않았습니다."))

        for hit in narrative_hits:
            accounts_text = ", ".join(
                f"{name} {growth:+.1f}%" for name, growth in hit.matched_accounts.items()
            )
            self._content_layout.addWidget(
                _card(
                    f"{hit.label}  ·  Priority Score {hit.priority_score:.1f}",
                    accounts_text,
                    hit.narrative,
                    "#1565c0",
                )
            )

        rule_hits = detect_relationship_rules(year_map, latest, prior)
        section2 = QLabel(f"Relationship Rule — Attention Pattern ({len(rule_hits)}건)")
        section2.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 16px;")
        self._content_layout.addWidget(section2)

        if not rule_hits:
            self._content_layout.addWidget(QLabel("주목할 만한 Attention Pattern이 발견되지 않았습니다."))

        for hit in rule_hits:
            evidence_text = ", ".join(f"{k} {v:+.1f}%" for k, v in hit.evidence.items())
            self._content_layout.addWidget(_card(hit.label, evidence_text, hit.description, "#ef6c00"))

        self._content_layout.addStretch()
