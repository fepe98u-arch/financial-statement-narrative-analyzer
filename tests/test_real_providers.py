"""OpenDART and Naver News are real external APIs — these tests only run
their live-call path when credentials are actually configured (matching
the same skip pattern used for PostgreSQL and the local embedding model).
The credential-missing path is tested unconditionally, since it needs no
network access at all."""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.public_data_collector.dart_provider import MissingCredentialError as DartMissingCredentialError
from app.public_data_collector.dart_provider import OpenDartProvider
from app.public_data_collector.news_provider import MissingCredentialError as NewsMissingCredentialError
from app.public_data_collector.news_provider import NaverNewsProvider
from app.public_data_collector.schemas import PublicCollectionRequest


def test_dart_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    provider = OpenDartProvider(api_key=None)
    request = PublicCollectionRequest(public_company_name="ABC Manufacturing", dart_corp_code="00126380")
    with pytest.raises(DartMissingCredentialError):
        provider.fetch(request)


def test_news_provider_requires_credentials(monkeypatch):
    # Explicit None still falls back to the environment inside
    # NaverNewsProvider.__init__, so a real local .env would otherwise mask
    # this test — isolate it properly instead of relying on nothing being
    # configured.
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    provider = NaverNewsProvider(client_id=None, client_secret=None)
    request = PublicCollectionRequest(public_company_name="ABC Manufacturing")
    with pytest.raises(NewsMissingCredentialError):
        provider.fetch(request)


def _fake_response():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"items": []}
    return resp


def test_news_provider_query_includes_topic_keyword_when_given():
    provider = NaverNewsProvider(client_id="x", client_secret="y")
    request = PublicCollectionRequest(public_company_name="LG에너지솔루션", topic_keyword="이자비용")
    with patch("app.public_data_collector.news_provider.requests.get", return_value=_fake_response()) as mock_get:
        provider.fetch(request)
    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["query"] == "LG에너지솔루션 이자비용"


def test_news_provider_query_is_company_name_only_without_topic_keyword():
    provider = NaverNewsProvider(client_id="x", client_secret="y")
    request = PublicCollectionRequest(public_company_name="LG에너지솔루션")
    with patch("app.public_data_collector.news_provider.requests.get", return_value=_fake_response()) as mock_get:
        provider.fetch(request)
    sent_params = mock_get.call_args.kwargs["params"]
    assert sent_params["query"] == "LG에너지솔루션"


def test_dart_provider_live_call_or_skip():
    if not os.environ.get("DART_API_KEY"):
        pytest.skip("DART_API_KEY not set — see .env template / PROJECT_SPEC.md section 24")
    provider = OpenDartProvider()
    request = PublicCollectionRequest(
        public_company_name="ABC Manufacturing", dart_corp_code="00126380", date_from="2025-01-01", date_to="2026-08-11"
    )
    results = provider.fetch(request)
    assert isinstance(results, list)


def test_news_provider_live_call_or_skip():
    if not (os.environ.get("NAVER_CLIENT_ID") and os.environ.get("NAVER_CLIENT_SECRET")):
        pytest.skip("NAVER_CLIENT_ID/SECRET not set — see .env template / PROJECT_SPEC.md section 25")
    provider = NaverNewsProvider()
    request = PublicCollectionRequest(public_company_name="삼성전자")
    results = provider.fetch(request)
    assert isinstance(results, list)
