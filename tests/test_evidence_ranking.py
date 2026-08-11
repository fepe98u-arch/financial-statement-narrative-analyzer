import pytest

from app.analysis.embedding_engine import LocalModelNotInstalledError, load_model
from app.analysis.evidence_ranking import EvidenceClassification, classify_similarity
from app.config import get_local_ai_model_path
from app.data.synthetic_public_documents import documents_for_company


def test_classify_similarity_never_auto_assigns_supported_or_conflicting():
    # These two are reserved for human review (module docstring) — the
    # automatic classifier must never produce them on its own.
    for score in (0.0, 0.2, 0.35, 0.5, 0.8, 0.99, 1.0):
        result = classify_similarity(score)
        assert result in (EvidenceClassification.POSSIBLE, EvidenceClassification.NO_EVIDENCE_FOUND)


def test_low_similarity_is_no_evidence_found():
    assert classify_similarity(0.0) == EvidenceClassification.NO_EVIDENCE_FOUND


def test_high_similarity_is_possible_not_supported():
    assert classify_similarity(0.9) == EvidenceClassification.POSSIBLE


def _local_model_or_skip():
    path = get_local_ai_model_path()
    try:
        return load_model(path)
    except LocalModelNotInstalledError as exc:
        pytest.skip(f"No local embedding model configured yet: {exc}")


def test_rank_public_evidence_against_a_live_local_model():
    from app.analysis.evidence_ranking import rank_public_evidence

    model = _local_model_or_skip()
    docs = documents_for_company("ABC Manufacturing")
    matches = rank_public_evidence(model, "생산시설 또는 사업 확장이 있었는가?", docs, top_k=3)

    assert len(matches) == 3
    assert matches[0].similarity >= matches[-1].similarity
