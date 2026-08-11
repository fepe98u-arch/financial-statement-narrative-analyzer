"""Provider interface every real or fake Public Data Collector implements
(PROJECT_SPEC.md section 23). Deliberately imports nothing from the private
analysis engines — see this package's __init__.py docstring and section 22.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.public_data_collector.schemas import PublicCollectionRequest


class PublicDataProvider(ABC):
    @abstractmethod
    def fetch(self, request: PublicCollectionRequest) -> list[dict]:
        """Returns a list of plain dicts describing public documents
        (source, title, published_at, url, public_document_id,
        public_company, snippet/content) — see section 26."""
