"""PROJECT_SPEC.md section 21: the ONLY shape a request into the Public
Data Collector may take. It's a plain frozen dataclass with no **kwargs, so
passing anything not listed here is a TypeError at construction time —
Python's own type system is the first enforcement layer, before the
Network Guard even runs.
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOWED_OUTBOUND_FIELDS = frozenset(
    {"public_company_name", "public_company_identifier", "dart_corp_code", "date_from", "date_to", "page", "page_size"}
)


@dataclass(frozen=True)
class PublicCollectionRequest:
    public_company_name: str
    public_company_identifier: str | None = None
    dart_corp_code: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = 1
    page_size: int = 20

    def to_outbound_payload(self) -> dict:
        """What would actually go out over the wire — never the request
        object itself, so nothing besides these fields can leak by
        accident even if the dataclass grows fields later."""
        return {
            "public_company_name": self.public_company_name,
            "public_company_identifier": self.public_company_identifier,
            "dart_corp_code": self.dart_corp_code,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "page": self.page,
            "page_size": self.page_size,
        }
