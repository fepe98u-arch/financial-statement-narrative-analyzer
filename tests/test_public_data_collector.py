"""Automated versions of PROJECT_SPEC.md sections 22, 36-38, and 54's
Source Code Network Audit — these run on every test invocation instead of
being a one-time manual check at the end of the project.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.public_data_collector.fake_provider import FakeDartProvider, FakeNewsProvider
from app.public_data_collector.network_guard import SecurityException, validate_outbound_request
from app.public_data_collector.schemas import PublicCollectionRequest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
COLLECTOR_ROOT = APP_ROOT / "public_data_collector"

FORBIDDEN_PRIVATE_IMPORTS = (
    "FinancialStatement",
    "DetectedPattern",
    "InvestigationQuestion",
    "PrivateAnalysisResult",
    "HumanReview",
)
FORBIDDEN_NETWORK_TOKENS = ("requests", "httpx", "urllib.request", "aiohttp", "socket.", "websocket")


def test_request_schema_rejects_unknown_fields():
    with pytest.raises(TypeError):
        PublicCollectionRequest(public_company_name="ABC Manufacturing", detected_pattern="should not be allowed")


def test_network_guard_rejects_private_fields():
    with pytest.raises(SecurityException):
        validate_outbound_request({"public_company_name": "ABC", "investigation_question": "생산시설 확대가 있었는가?"})


def test_network_guard_allows_only_allowlisted_fields():
    payload = validate_outbound_request(
        {"public_company_name": "ABC Manufacturing", "date_from": "2025-01-01", "date_to": "2026-08-11", "page": 1, "page_size": 20}
    )
    assert payload["public_company_name"] == "ABC Manufacturing"


def test_network_guard_blocks_secret_leakage(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "super-secret-value-123")
    with pytest.raises(SecurityException):
        validate_outbound_request({"public_company_name": "super-secret-value-123 leaked"})


def test_fake_providers_return_data_without_network_and_respect_allowlist():
    request = PublicCollectionRequest(public_company_name="ABC Manufacturing", date_from="2025-01-01", date_to="2026-08-11")

    news = FakeNewsProvider().fetch(request)
    dart = FakeDartProvider().fetch(request)

    assert news, "expected at least one fake news document"
    assert dart, "expected at least one fake DART document"
    assert all(d["public_company"] == "ABC Manufacturing" for d in news + dart)


def test_public_data_collector_package_never_imports_private_analysis_objects():
    for path in COLLECTOR_ROOT.glob("*.py"):
        import_lines = [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        for line in import_lines:
            for forbidden in FORBIDDEN_PRIVATE_IMPORTS:
                assert forbidden not in line, f"{path.name} must not import {forbidden} (PROJECT_SPEC.md section 22): {line}"


def test_only_public_data_collector_package_may_reference_network_libraries():
    for path in APP_ROOT.rglob("*.py"):
        if COLLECTOR_ROOT in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_NETWORK_TOKENS:
            assert token not in source, (
                f"{path.relative_to(APP_ROOT)} references '{token}' — network code may only live in "
                "app/public_data_collector/ (PROJECT_SPEC.md sections 23, 54)"
            )
