from app.analysis.document_parsing import chunk_document, chunk_text, parse_and_chunk_all, parse_document
from app.data.synthetic_public_documents import SYNTHETIC_PUBLIC_DOCUMENTS, documents_for_company


def test_documents_for_company_filters_correctly():
    abc_docs = documents_for_company("ABC Manufacturing")
    assert len(abc_docs) > 0
    assert all(d.public_company == "ABC Manufacturing" for d in abc_docs)


def test_chunk_text_covers_full_text_with_overlap():
    text = "가" * 300
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    # every character index should be covered by at least one chunk
    reconstructed = chunks[0]
    assert reconstructed.startswith("가")


def test_chunk_text_short_text_returns_single_chunk():
    assert chunk_text("짧은 텍스트", chunk_size=100, overlap=20) == ["짧은 텍스트"]


def test_parse_document_normalizes_whitespace():
    doc = SYNTHETIC_PUBLIC_DOCUMENTS[0]
    parsed = parse_document(doc)
    assert "  " not in parsed.text
    assert parsed.document_id == doc.public_document_id


def test_chunk_document_ids_are_stable_and_unique():
    doc = SYNTHETIC_PUBLIC_DOCUMENTS[0]
    parsed = parse_document(doc)
    chunks = chunk_document(parsed)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_parse_and_chunk_all_produces_chunks_for_every_document():
    chunks = parse_and_chunk_all(SYNTHETIC_PUBLIC_DOCUMENTS)
    document_ids_with_chunks = {c.document_id for c in chunks}
    assert document_ids_with_chunks == {d.public_document_id for d in SYNTHETIC_PUBLIC_DOCUMENTS}
