"""One file per PROJECT_SPEC.md section 53's 17-point checklist. Several
points are already covered elsewhere (noted below) — this file either
re-asserts them directly or points at the file that does, so the checklist
itself is auditable in one place instead of scattered.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.fake_provider import FakeNewsProvider
from app.public_data_collector.network_guard import SecurityException, validate_outbound_request
from app.public_data_collector.schemas import PublicCollectionRequest
from app.security_logging import LOG_FILE, log_event


# 1. 프로그램 시작 시 Private Analysis는 Local Only
def test_01_private_analysis_engines_have_no_network_imports():
    # Enforced continuously by test_public_data_collector.py::
    # test_only_public_data_collector_package_may_reference_network_libraries
    from app.analysis import metrics_engine, narrative_patterns, relationship_rules

    for module in (metrics_engine, narrative_patterns, relationship_rules):
        assert not hasattr(module, "requests")


# 2. 프로그램 시작 시 Public Collection 자동 실행 안 됨
def test_02_public_data_page_never_fetches_on_construction():
    with patch.object(FakeNewsProvider, "fetch") as mock_fetch:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from app.ui.pages.public_data_page import PublicDataPage

        PublicDataPage()
        mock_fetch.assert_not_called()


# 3-6. 재무제표/Detected Pattern/Investigation Question/Internal Hypothesis가
# Outbound Request에 포함되지 않음
@pytest.mark.parametrize(
    "forbidden_field",
    ["financial_statement", "financial_amount", "detected_pattern", "investigation_question", "internal_hypothesis", "internal_summary", "audit_comment"],
)
def test_03_to_06_private_fields_are_rejected_by_network_guard(forbidden_field):
    with pytest.raises(SecurityException):
        validate_outbound_request({"public_company_name": "ABC", forbidden_field: "should never leave the machine"})


# 7. Public Data Collector가 허용 Schema 외 필드를 받지 못함
def test_07_request_schema_has_no_kwargs_escape_hatch():
    with pytest.raises(TypeError):
        PublicCollectionRequest(public_company_name="ABC", extra_field="not allowed")


# 8-9. 다른 Module에서 직접 HTTP 요청을 하지 않음 / External Request는
# Public Data Collector에서만 발생
def test_08_09_network_audit():
    # See test_public_data_collector.py::
    # test_only_public_data_collector_package_may_reference_network_libraries
    # for the full-source scan; here we just confirm the collector package
    # is where the network libraries actually live.
    collector_source = (Path(__file__).resolve().parents[1] / "app" / "public_data_collector").glob("*.py")
    assert any("import requests" in p.read_text(encoding="utf-8") for p in collector_source)


# 10-11. API Key / Private Financial Amount가 로그에 기록되지 않음
def test_10_11_log_event_signature_has_no_room_for_secrets_or_amounts(tmp_path, monkeypatch):
    import app.security_logging as security_logging

    log_path = tmp_path / "security_events.log"
    monkeypatch.setattr(security_logging, "LOG_FILE", log_path)
    monkeypatch.setattr(security_logging, "_logger", __import__("logging").getLogger("fsna.security.test"))

    with pytest.raises(TypeError):
        log_event("TEST_EVENT", success=True, api_key="sk-should-not-be-loggable")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        log_event("TEST_EVENT", success=True, financial_amount=123456)  # type: ignore[call-arg]


def test_10_11_log_event_only_writes_allowlisted_fields():
    log_event("TEST_EVENT", success=True, provider="test", records_count=3)
    assert LOG_FILE.exists()
    last_line = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
    entry = json.loads(last_line)
    assert set(entry.keys()) == {"timestamp", "event_type", "success", "provider", "error_code", "records_count"}


# 12. Local Embedding이 외부 API를 호출하지 않음
def test_12_local_embedding_forces_offline_env_vars():
    import app.analysis.embedding_engine  # noqa: F401  (import triggers the setdefault calls)

    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"


# 13. Local RAG가 외부 API를 호출하지 않음
def test_13_evidence_ranking_has_no_network_imports():
    from app.analysis import evidence_ranking

    source = Path(evidence_ranking.__file__).read_text(encoding="utf-8")
    for token in ("requests", "httpx", "urllib.request", "aiohttp"):
        assert token not in source


# 14. PostgreSQL이 localhost를 사용
def test_14_database_url_defaults_to_localhost():
    from app.db.connection import DEFAULT_DATABASE_URL

    assert "127.0.0.1" in DEFAULT_DATABASE_URL


# 15. Synthetic Pattern Detection 정상
def test_15_synthetic_pattern_detection_runs():
    # Full coverage in tests/test_engines.py
    from app.analysis.narrative_patterns import detect_narrative_patterns
    from app.data.loader import load_financial_facts, to_year_map

    year_map = to_year_map(load_financial_facts(), "ABC Manufacturing")
    assert detect_narrative_patterns(year_map, 2026, 2025)


# 16. Historical Pattern 정상
def test_16_historical_pattern_runs():
    # Full coverage in tests/test_phase3.py
    from app.analysis.historical_patterns import classify_account_history
    from app.data.loader import load_financial_facts, to_year_map

    year_map = to_year_map(load_financial_facts(), "ABC Manufacturing")
    result = classify_account_history(year_map, "INVENTORY", "재고자산", [2022, 2023, 2024, 2025, 2026])
    assert result is not None


# 17. Public Article Ranking 정상 (structure always testable; live ranking
# needs a local model — see tests/test_evidence_ranking.py which skips
# gracefully without one)
def test_17_public_article_ranking_inputs_are_available():
    docs = documents_for_company("ABC Manufacturing")
    assert len(docs) >= 2
