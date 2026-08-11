"""OpenDART Provider (PROJECT_SPEC.md section 24) — Phase 8.

The only place in this codebase that actually calls opendart.fss.or.kr.
Requires a real DART_API_KEY (free, from https://opendart.fss.or.kr/) —
this raises MissingCredentialError rather than silently returning an empty
list when the key is absent, so "no key configured" is never mistaken for
"no disclosures found".

Only public_company_name/dart_corp_code/date_from/date_to/page/page_size
ever reach the request — validate_outbound_request() enforces that before
any HTTP call, exactly as it does for the fake providers.
"""
from __future__ import annotations

import os

import requests

from app.public_data_collector.base import PublicDataProvider
from app.public_data_collector.network_guard import validate_outbound_request
from app.public_data_collector.schemas import PublicCollectionRequest
from app.security_logging import log_event

DART_LIST_ENDPOINT = "https://opendart.fss.or.kr/api/list.json"


class MissingCredentialError(RuntimeError):
    pass


class OpenDartProvider(PublicDataProvider):
    def __init__(self, api_key: str | None = None, timeout_seconds: float = 10.0) -> None:
        self._api_key = api_key or os.environ.get("DART_API_KEY")
        self._timeout_seconds = timeout_seconds

    def fetch(self, request: PublicCollectionRequest) -> list[dict]:
        if not self._api_key:
            raise MissingCredentialError(
                "DART_API_KEY is not set. Get a free key at https://opendart.fss.or.kr/ "
                "and add DART_API_KEY=... to .env."
            )
        if not request.dart_corp_code:
            raise ValueError("OpenDartProvider requires request.dart_corp_code.")

        outbound = validate_outbound_request(request.to_outbound_payload())

        # crtfc_key is DART's own required auth credential (a technical
        # parameter to reach a public endpoint, section 2), not private
        # analysis data — it's added after the allowlist check, not
        # smuggled through it.
        params = {
            "crtfc_key": self._api_key,
            "corp_code": outbound["dart_corp_code"],
            "bgn_de": (outbound["date_from"] or "").replace("-", ""),
            "end_de": (outbound["date_to"] or "").replace("-", ""),
            "page_no": outbound["page"],
            "page_count": outbound["page_size"],
        }

        try:
            response = requests.get(DART_LIST_ENDPOINT, params=params, timeout=self._timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            log_event("PUBLIC_DATA_FETCH", success=False, provider="dart", error_code=type(exc).__name__)
            raise

        if data.get("status") != "000":
            log_event("PUBLIC_DATA_FETCH", success=False, provider="dart", error_code=data.get("status"))
            raise RuntimeError(f"OpenDART API error {data.get('status')}: {data.get('message')}")

        results = [
            {
                "public_document_id": item.get("rcept_no"),
                "source": "dart",
                "title": item.get("report_nm"),
                "published_at": item.get("rcept_dt"),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no')}",
                "public_company": item.get("corp_name"),
                "snippet": item.get("report_nm"),
            }
            for item in data.get("list", [])
        ]
        log_event("PUBLIC_DATA_FETCH", success=True, provider="dart", records_count=len(results))
        return results
