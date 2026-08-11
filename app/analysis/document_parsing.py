"""Local Document Parsing + Chunking (PROJECT_SPEC.md sections 8, 30).

Structured Excel/CSV is the priority per section 8 (no PDF OCR yet); this
module handles the plain-text public documents from Phase 5's synthetic
dataset the same way real fetched articles/filings will be handled once
Phase 7-9 exist. Everything here runs on text already sitting on disk/in
memory — no I/O, local or otherwise.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.data.synthetic_public_documents import PublicDocument

DEFAULT_CHUNK_SIZE = 120
DEFAULT_CHUNK_OVERLAP = 20


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    title: str
    published_at: str
    public_company: str
    text: str


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str


def parse_document(doc: PublicDocument) -> ParsedDocument:
    normalized = re.sub(r"\s+", " ", doc.content).strip()
    return ParsedDocument(doc.public_document_id, doc.title, doc.published_at, doc.public_company, normalized)


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


def chunk_document(parsed: ParsedDocument, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[DocumentChunk]:
    return [
        DocumentChunk(f"{parsed.document_id}-{i}", parsed.document_id, i, text)
        for i, text in enumerate(chunk_text(parsed.text, chunk_size, overlap))
    ]


def parse_and_chunk_all(docs: list[PublicDocument]) -> list[DocumentChunk]:
    chunks = []
    for doc in docs:
        parsed = parse_document(doc)
        chunks.extend(chunk_document(parsed))
    return chunks
