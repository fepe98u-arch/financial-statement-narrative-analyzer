"""News Provider (PROJECT_SPEC.md section 25) — Phase 9.

Uses the NAVER API HUB news search endpoint (NAVER Cloud Platform). The old
developers.naver.com Search API stopped accepting new applications on
2026-07-31 and is being migrated to NAVER API HUB — see
https://developers.naver.com/notice/article/32530. New/renewed credentials
come from the NCP console (NAVER API HUB > Application > 인증 정보), not
the old developer site, and use different header names.

The search query is *only* the company name — section 25 explicitly
forbids ever appending keywords derived from internal patterns
("시설투자", "재고", "차입금" etc.), so there is no parameter here that
could carry one even if a caller tried; the query is hardcoded to
`request.public_company_name`.

Requires NAVER_CLIENT_ID / NAVER_CLIENT_SECRET — raises
MissingCredentialError rather than silently returning nothing.
"""
from __future__ import annotations

import os
import re

import requests

from app.public_data_collector.base import PublicDataProvider
from app.public_data_collector.network_guard import validate_outbound_request
from app.public_data_collector.schemas import PublicCollectionRequest
from app.security_logging import log_event

NAVER_NEWS_ENDPOINT = "https://naverapihub.apigw.ntruss.com/search/v1/news"


class MissingCredentialError(RuntimeError):
    pass


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


class NaverNewsProvider(PublicDataProvider):
    def __init__(self, client_id: str | None = None, client_secret: str | None = None, timeout_seconds: float = 10.0) -> None:
        self._client_id = client_id or os.environ.get("NAVER_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET")
        self._timeout_seconds = timeout_seconds

    def fetch(self, request: PublicCollectionRequest) -> list[dict]:
        if not self._client_id or not self._client_secret:
            raise MissingCredentialError(
                "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET is not set. Get credentials from the NCP "
                "console (NAVER API HUB > Application > 인증 정보) and add them to .env."
            )

        outbound = validate_outbound_request(request.to_outbound_payload())

        headers = {"X-NCP-APIGW-API-KEY-ID": self._client_id, "X-NCP-APIGW-API-KEY": self._client_secret}
        params = {
            "query": outbound["public_company_name"],  # company name ONLY — section 25
            "display": min(outbound["page_size"], 100),
            "start": max(1, (outbound["page"] - 1) * outbound["page_size"] + 1),
            "sort": "date",
            "format": "json",
        }

        try:
            response = requests.get(NAVER_NEWS_ENDPOINT, headers=headers, params=params, timeout=self._timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            log_event("PUBLIC_DATA_FETCH", success=False, provider="naver-news", error_code=type(exc).__name__)
            raise

        results = [
            {
                "public_document_id": item.get("link"),
                "source": "naver-news",
                "title": _strip_html(item.get("title")),
                "published_at": item.get("pubDate"),
                "url": item.get("link"),
                "public_company": request.public_company_name,
                "snippet": _strip_html(item.get("description")),
            }
            for item in data.get("items", [])
        ]
        log_event("PUBLIC_DATA_FETCH", success=True, provider="naver-news", records_count=len(results))
        return results
