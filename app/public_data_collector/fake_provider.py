"""Fake providers for Phase 7 (PROJECT_SPEC.md section 57: "Phase 7에서는
아직 실제 인터넷 연결을 하지 않는다. Fake Provider로 테스트한다.").

These simulate what OpenDartProvider (Phase 8) and NewsProvider (Phase 9)
will eventually return, sourced entirely from the Phase 5 synthetic
document fixture — zero network I/O. The point is to prove the
request -> Network Guard -> response shape works before any real HTTP call
exists anywhere in the codebase.
"""
from __future__ import annotations

from app.data.synthetic_public_documents import documents_for_company
from app.public_data_collector.base import PublicDataProvider
from app.public_data_collector.network_guard import validate_outbound_request
from app.public_data_collector.schemas import PublicCollectionRequest
from app.security_logging import log_event


def _document_to_dict(doc) -> dict:
    return {
        "public_document_id": doc.public_document_id,
        "source": doc.source,
        "title": doc.title,
        "published_at": doc.published_at,
        "url": doc.url,
        "public_company": doc.public_company,
        "snippet": doc.snippet,
    }


class FakeNewsProvider(PublicDataProvider):
    def fetch(self, request: PublicCollectionRequest) -> list[dict]:
        validate_outbound_request(request.to_outbound_payload())
        docs = [d for d in documents_for_company(request.public_company_name) if d.source == "synthetic-news"]
        results = [_document_to_dict(d) for d in docs[: request.page_size]]
        log_event("PUBLIC_DATA_FETCH", success=True, provider="fake-news", records_count=len(results))
        return results


class FakeDartProvider(PublicDataProvider):
    def fetch(self, request: PublicCollectionRequest) -> list[dict]:
        validate_outbound_request(request.to_outbound_payload())
        docs = [d for d in documents_for_company(request.public_company_name) if d.source == "synthetic-dart"]
        results = [_document_to_dict(d) for d in docs[: request.page_size]]
        log_event("PUBLIC_DATA_FETCH", success=True, provider="fake-dart", records_count=len(results))
        return results
