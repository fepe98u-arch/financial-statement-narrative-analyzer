"""Desktop shell: security status bar + left sidebar navigation + pages.

Sidebar items follow PROJECT_SPEC.md section 45. The only network code in
the project lives in the isolated `app/public_data_collector/` module and
only runs when a user explicitly triggers a fetch — nothing here
auto-connects, so the status bar's "PUBLIC DATA COLLECTION: OFF" is always
accurate on startup.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.pages.account_mapping_page import AccountMappingPage
from app.ui.pages.attention_patterns_page import AttentionPatternsPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.evidence_analysis_page import EvidenceAnalysisPage
from app.ui.pages.financial_trend_page import FinancialTrendPage
from app.ui.pages.historical_analysis_page import HistoricalAnalysisPage
from app.ui.pages.human_review_page import HumanReviewPage
from app.ui.pages.investigation_questions_page import InvestigationQuestionsPage
from app.ui.pages.placeholder_page import PlaceholderPage
from app.ui.pages.public_data_page import PublicDataPage
from app.ui.pages.statement_import_page import StatementImportPage

# (sidebar label, page factory) — matches PROJECT_SPEC.md section 45 order.
# Anything not implemented yet renders as a clearly-labeled placeholder
# instead of pretending to exist.
SIDEBAR_PAGES: list[tuple[str, callable]] = [
    ("Dashboard", DashboardPage),
    ("재무제표 불러오기", StatementImportPage),
    ("Account Mapping", AccountMappingPage),
    ("Financial Trend", FinancialTrendPage),
    ("Attention Patterns", AttentionPatternsPage),
    ("Historical Analysis", HistoricalAnalysisPage),
    ("Investigation Questions", InvestigationQuestionsPage),
    ("Public Data", PublicDataPage),
    ("Evidence Analysis", EvidenceAnalysisPage),
    ("Human Review", HumanReviewPage),
    ("Database", lambda: PlaceholderPage("Database", "Phase 4 저장 로직은 준비됨 — SETUP_POSTGRESQL.md로 로컬 서버 연결 후 이용 가능")),
    ("Security", lambda: PlaceholderPage("Security", "Phase 10에서 구현 예정")),
]


class SecurityStatusBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        private_label = QLabel("\U0001f512 PRIVATE ANALYSIS: LOCAL ONLY")
        private_label.setStyleSheet(
            "color: white; background-color: #1b5e20; padding: 4px 10px;"
            " border-radius: 4px; font-weight: bold;"
        )

        public_label = QLabel("\U0001f310 PUBLIC DATA COLLECTION: OFF")
        public_label.setStyleSheet(
            "color: white; background-color: #555555; padding: 4px 10px;"
            " border-radius: 4px; font-weight: bold;"
        )

        layout.addWidget(private_label)
        layout.addWidget(public_label)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Financial Statement Narrative Analyzer")
        self.resize(1150, 680)

        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(SecurityStatusBar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(190)
        self._stack = QStackedWidget()

        for label, factory in SIDEBAR_PAGES:
            self._sidebar.addItem(QListWidgetItem(label))
            self._stack.addWidget(factory())

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        body.addWidget(self._sidebar)
        body.addWidget(self._stack, stretch=1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        outer_layout.addWidget(body_widget, stretch=1)

        self.setCentralWidget(central)
