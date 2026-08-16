"""Human Review page (PROJECT_SPEC.md sections 39, 49).

Degrades gracefully: if the local PostgreSQL server isn't running, the page
still shows the current patterns read-only and explains what's needed to
enable saving reviews — it does not crash the app (same philosophy as
section 41's "core features work without Local AI").
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import list_companies, load_financial_facts, to_year_map, years_for_company
from app.db.connection import CloudDatabaseNotAllowedError, build_engine, get_database_url
from app.db.repository import PatternReviewStatus, check_connection, get_latest_human_reviews, init_schema, save_human_review


class HumanReviewPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._facts = load_financial_facts()
        self._companies = list_companies(self._facts)

        self._engine = None
        self._connected = False
        self._connection_message = ""
        self._try_connect()

        outer = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("회사:"))
        self._company_combo = QComboBox()
        self._company_combo.addItems(self._companies)
        self._company_combo.currentTextChanged.connect(self._render)
        header.addWidget(self._company_combo)

        refresh_btn = QPushButton("DB 연결 다시 확인")
        refresh_btn.clicked.connect(self._reconnect_and_render)
        header.addWidget(refresh_btn)
        header.addStretch()
        outer.addLayout(header)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        outer.addWidget(self._status_label)

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

    def _try_connect(self) -> None:
        try:
            engine = build_engine()
        except CloudDatabaseNotAllowedError as exc:
            self._engine, self._connected, self._connection_message = None, False, str(exc)
            return

        ok, message = check_connection(engine)
        if ok:
            init_schema(engine)
        self._engine, self._connected, self._connection_message = engine, ok, message

    def _reconnect_and_render(self) -> None:
        self._try_connect()
        self._render(self._company_combo.currentText())

    def _update_status_label(self) -> None:
        if self._connected:
            self._status_label.setText(f"\U0001f7e2 PostgreSQL 연결됨 ({get_database_url()}) — 리뷰 저장 가능")
            self._status_label.setStyleSheet("color: #1b5e20; margin: 6px 0;")
        else:
            self._status_label.setText(
                "\U0001f534 PostgreSQL에 연결할 수 없습니다. 아래 목록은 읽기 전용으로 표시됩니다.\n"
                f"오류: {self._connection_message}\n"
                "로컬 PostgreSQL 설치·설정 방법은 SETUP_POSTGRESQL.md를 참고하세요."
            )
            self._status_label.setStyleSheet("color: #b71c1c; margin: 6px 0;")

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render(self, company: str) -> None:
        self._update_status_label()
        self._clear_content()

        years = years_for_company(self._facts, company)
        if len(years) < 2:
            self._content_layout.addWidget(QLabel("이 회사는 연도가 2개 미만이라 리뷰할 Pattern이 없습니다."))
            self._content_layout.addStretch()
            return

        latest, prior = years[-1], years[-2]
        year_map = to_year_map(self._facts, company)
        narrative_hits = detect_narrative_patterns(year_map, latest, prior)
        rule_hits = detect_relationship_rules(year_map, latest, prior)

        existing_reviews = {}
        if self._connected:
            existing_reviews = get_latest_human_reviews(self._engine, "DETECTED_PATTERN")

        for pattern_type, hit, key, label, description in [
            ("NARRATIVE_CLUSTER", hit, hit.cluster_id, hit.label, hit.narrative) for hit in narrative_hits
        ] + [
            ("RELATIONSHIP_RULE", hit, hit.rule_id, hit.label, hit.description) for hit in rule_hits
        ]:
            target_id = f"{company}:{pattern_type}:{key}"
            self._content_layout.addWidget(
                self._build_card(target_id, label, description, existing_reviews.get(target_id))
            )

        if not narrative_hits and not rule_hits:
            self._content_layout.addWidget(QLabel("현재 리뷰할 Pattern이 없습니다."))

        self._content_layout.addStretch()

    def _build_card(self, target_id: str, label: str, description: str, existing_review) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #fafafa; border-left: 4px solid #6a1b9a;"
            " border-radius: 4px; padding: 10px; margin-bottom: 8px; }"
        )
        layout = QVBoxLayout(frame)

        title = QLabel(label)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(description)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        row = QHBoxLayout()
        combo = QComboBox()
        combo.addItems([s.value for s in PatternReviewStatus])
        if existing_review is not None:
            combo.setCurrentText(existing_review.status)
        row.addWidget(combo)

        save_btn = QPushButton("저장")
        save_btn.setEnabled(self._connected)
        save_btn.clicked.connect(lambda: self._save(target_id, combo.currentText(), save_btn))
        row.addWidget(save_btn)
        row.addStretch()
        layout.addLayout(row)

        return frame

    def _save(self, target_id: str, status: str, button: QPushButton) -> None:
        if not self._connected:
            return
        save_human_review(self._engine, "DETECTED_PATTERN", target_id, status)
        button.setText("저장됨 ✓")
