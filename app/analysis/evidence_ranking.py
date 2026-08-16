"""Local Relevance Matching + Local RAG + Evidence Classification
(PROJECT_SPEC.md sections 27, 29-31).

Everything here runs after public documents are already sitting on the
local disk (from the synthetic fixture today, from a real Public Data
Collector run from Phase 7+ onward) — nothing in this module performs I/O.

Evidence Classification is intentionally conservative: the engine only ever
auto-assigns NO_EVIDENCE_FOUND or POSSIBLE. SUPPORTED and
CONFLICTING_EVIDENCE are reserved for a human reviewer to assign (section
31's own example shows a single matching article should stay POSSIBLE, not
be auto-escalated to a confirmed cause).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.analysis.document_parsing import DocumentChunk, chunk_document, parse_document
from app.analysis.embedding_engine import cosine_similarities, embed_texts
from app.data.synthetic_public_documents import PublicDocument

POSSIBLE_THRESHOLD = 0.35  # cosine similarity; tune once a real model is in use


class EvidenceClassification(str, Enum):
    SUPPORTED = "SUPPORTED"  # human-assigned only, see module docstring
    POSSIBLE = "POSSIBLE"
    NO_EVIDENCE_FOUND = "NO_EVIDENCE_FOUND"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"  # human-assigned only


@dataclass(frozen=True)
class EvidenceMatch:
    document_id: str
    title: str
    source: str
    published_at: str
    chunk: DocumentChunk
    similarity: float
    classification: EvidenceClassification
    url: str = ""


def classify_similarity(similarity: float) -> EvidenceClassification:
    return EvidenceClassification.POSSIBLE if similarity >= POSSIBLE_THRESHOLD else EvidenceClassification.NO_EVIDENCE_FOUND


def documents_from_provider_results(results: list[dict]) -> list[PublicDocument]:
    """Adapts a Public Data Collector provider's plain-dict results (see
    app/public_data_collector/base.py — same shape for the fake and real
    providers) into PublicDocument instances so real fetched articles go
    through the exact same local ranking pipeline as the synthetic fixture.
    `content` is whatever text the provider actually returned (a snippet,
    per section 26 — no full-text scraping), never the full article body."""
    return [
        PublicDocument(
            public_document_id=r.get("public_document_id") or r.get("url") or "",
            source=r.get("source", ""),
            title=r.get("title", ""),
            published_at=r.get("published_at", ""),
            url=r.get("url", ""),
            public_company=r.get("public_company", ""),
            content=r.get("snippet") or r.get("content") or "",
        )
        for r in results
    ]


def rank_public_evidence(
    model, investigation_question: str, documents: list[PublicDocument], top_k: int = 5
) -> list[EvidenceMatch]:
    all_chunks: list[tuple[PublicDocument, DocumentChunk]] = []
    for doc in documents:
        parsed = parse_document(doc)
        for chunk in chunk_document(parsed):
            all_chunks.append((doc, chunk))

    if not all_chunks:
        return []

    query_vec = embed_texts(model, [investigation_question])[0]
    chunk_vecs = embed_texts(model, [chunk.text for _, chunk in all_chunks])
    similarities = cosine_similarities(query_vec, chunk_vecs)

    ranked = sorted(zip(all_chunks, similarities), key=lambda pair: pair[1], reverse=True)

    matches = []
    for (doc, chunk), score in ranked[:top_k]:
        matches.append(
            EvidenceMatch(
                document_id=doc.public_document_id,
                title=doc.title,
                source=doc.source,
                published_at=doc.published_at,
                chunk=chunk,
                similarity=round(float(score), 3),
                classification=classify_similarity(float(score)),
                url=doc.url,
            )
        )
    return matches
