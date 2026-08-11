"""Pattern Similarity (PROJECT_SPEC.md section 18).

Direction Similarity and Magnitude Similarity between two YoY-growth
snapshots of the same account set, always from a real formula — the spec is
explicit that AI must never invent a similarity number.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.metrics_engine import YearMap, growth_rate


@dataclass(frozen=True)
class PatternSimilarity:
    shared_accounts: list[str]
    direction_similarity_pct: float
    magnitude_similarity_pct: float


def compute_pattern_similarity(
    current: dict[str, float], historical: dict[str, float]
) -> PatternSimilarity | None:
    shared = sorted(set(current) & set(historical))
    if not shared:
        return None

    direction_matches = sum(1 for k in shared if (current[k] > 0) == (historical[k] > 0))
    direction_similarity = round(direction_matches / len(shared) * 100, 1)

    magnitude_scores = []
    for k in shared:
        c, h = current[k], historical[k]
        denom = max(abs(c), abs(h))
        magnitude_scores.append(100.0 if denom == 0 else max(0.0, 100 - abs(c - h) / denom * 100))
    magnitude_similarity = round(sum(magnitude_scores) / len(magnitude_scores), 1)

    return PatternSimilarity(shared, direction_similarity, magnitude_similarity)


def most_similar_historical_year(
    year_map: YearMap, account_codes: list[str], years: list[int]
) -> tuple[int, PatternSimilarity] | None:
    """Among every historical transition (every consecutive year pair before
    the latest one), find the one whose pattern is most similar to the
    latest transition, ranked by direction+magnitude similarity."""
    latest, prior = years[-1], years[-2]
    current = {
        code: g
        for code in account_codes
        if (g := growth_rate(year_map, code, latest, prior)) is not None
    }
    if not current:
        return None

    best: tuple[int, PatternSimilarity] | None = None
    for later, earlier in zip(years[1:-1], years[:-2]):
        historical = {
            code: g
            for code in account_codes
            if (g := growth_rate(year_map, code, later, earlier)) is not None
        }
        similarity = compute_pattern_similarity(current, historical)
        if similarity is None:
            continue
        score = similarity.direction_similarity_pct + similarity.magnitude_similarity_pct
        if best is None or score > (best[1].direction_similarity_pct + best[1].magnitude_similarity_pct):
            best = (later, similarity)

    return best
