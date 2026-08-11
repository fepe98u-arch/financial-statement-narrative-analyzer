"""OpenDART and Naver News are real external APIs — these tests only run
their live-call path when credentials are actually configured (matching
the same skip pattern used for PostgreSQL and the local embedding model).
The credential-missing path is tested unconditionally, since it needs no
network access at all."""
import os

import pytest

from app.public_data_collector.dart_provider import MissingCredentialError as DartMissingCredentialError
from app.public_data_collector.dart_provider import OpenDartProvider
from app.public_data_collector.news_provider import MissingCredentialError as NewsMissingCredentialError
from app.public_data_collector.news_provider import NaverNewsProvider
from app.public_data_collector.schemas import PublicCollectionRequest


def test_dart_provider_requires_api_key():
    provider = OpenDartProvider(api_key=None)
    request = PublicCollectionRequest(public_company_name="ABC Manufacturing", dart_corp_code="00126380")
    with pytest.raises(DartMissingCredentialError):
        provider.fetch(request)


def test_news_provider_requires_credentials():
    provider = NaverNewsProvider(client_id=None, client_secret=None)
    request = PublicCollectionRequest(public_company_name="ABC Manufacturing")
    with pytest.raises(NewsMissingCredentialError):
        provider.fetch(request)


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
