"""Business Narrative Pattern Engine (PROJECT_SPEC.md sections 14-16).

Looks across a *cluster* of related accounts (not every possible pair —
section 15) for a directionally coherent story worth reviewing, and scores
how worth-reviewing it is. The program never claims these accounts *must*
move together, and the score is not a fraud/error probability — it's a
"how much would a reviewer want to look at this first" ranking, built from
a real, reproducible formula (section 16 and 18 both insist on this: no
AI-invented numbers).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.metrics_engine import YearMap, growth_rate
from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES

NOTABLE_GROWTH_PCT = 15.0


@dataclass(frozen=True)
class ClusterDefinition:
    cluster_id: str
    label: str
    # account_code -> expected direction ("up" or "down")
    directions: dict[str, str]
    min_matched: int
    narrative: str
    # Used only when `directions` doesn't reach min_matched — e.g. a real
    # filing that reports 유형자산 as one combined line instead of breaking
    # it into STRUCTURE/MACHINERY/CONSTRUCTION_IN_PROGRESS (DART's summary
    # API does this; the detailed breakdown only exists in the filing's
    # notes). Evaluated as a fully separate, self-contained set — never
    # merged with `directions` — so a company that somehow has both never
    # double-counts the same underlying asset growth as two matches.
    fallback_directions: dict[str, str] | None = None
    fallback_min_matched: int | None = None


CLUSTER_DEFINITIONS: list[ClusterDefinition] = [
    ClusterDefinition(
        cluster_id="PRODUCTION_EXPANSION",
        label="생산·투자 확대 vs 재고 감소",
        directions={
            "INVENTORY": "down",
            "STRUCTURE": "up",
            "MACHINERY": "up",
            "CONSTRUCTION_IN_PROGRESS": "up",
            "LT_BORROWINGS": "up",
        },
        min_matched=3,
        narrative=(
            "생산 및 투자 관련 자산이 확대되는 가운데 재고자산은 감소했습니다. "
            "이러한 변화가 동일한 사업적 사건이나 사업전략 변화와 관련되어 있는지 "
            "추가적인 설명이 필요할 수 있습니다."
        ),
        fallback_directions={"INVENTORY": "down", "TANGIBLE_ASSETS": "up", "LT_BORROWINGS": "up"},
        fallback_min_matched=3,
    ),
    ClusterDefinition(
        cluster_id="CAPEX_FINANCING",
        label="CAPEX / FINANCING",
        directions={
            "STRUCTURE": "up",
            "MACHINERY": "up",
            "CONSTRUCTION_IN_PROGRESS": "up",
            "LT_BORROWINGS": "up",
        },
        min_matched=3,
        narrative=(
            "설비 관련 자산과 차입금이 함께 크게 증가했습니다. 신규 시설투자와 "
            "그 자금조달이 서로 연관된 사업적 사건인지 확인이 필요할 수 있습니다."
        ),
        fallback_directions={"TANGIBLE_ASSETS": "up", "LT_BORROWINGS": "up"},
        fallback_min_matched=2,
    ),
    ClusterDefinition(
        cluster_id="REVENUE_RECEIVABLE",
        label="Revenue / Receivable",
        directions={"SALES": "down", "RECEIVABLE": "up"},
        min_matched=2,
        narrative=(
            "매출은 감소했지만 매출채권은 증가했습니다. 매출 회수 지연이나 매출 "
            "인식 방식 변화와 관련이 있는지 확인이 필요할 수 있습니다."
        ),
    ),
    ClusterDefinition(
        cluster_id="CREDIT_RISK",
        label="Credit Risk",
        directions={"RECEIVABLE": "up", "ALLOWANCE_DOUBTFUL": "up"},
        min_matched=2,
        narrative=(
            "매출채권과 대손충당금이 함께 증가했습니다. 거래처의 신용위험 변화나 "
            "회수 가능성 평가 변화와 관련이 있는지 확인이 필요할 수 있습니다."
        ),
    ),
    ClusterDefinition(
        cluster_id="PROFIT_CASHFLOW",
        label="Profit / Cash Flow",
        directions={"NET_INCOME": "up", "OPERATING_CF": "down"},
        min_matched=2,
        narrative=(
            "순이익은 증가했지만 영업활동현금흐름은 감소했습니다. 손익과 "
            "현금흐름의 괴리 원인에 대한 확인이 필요할 수 있습니다."
        ),
    ),
]


@dataclass(frozen=True)
class NarrativePatternHit:
    cluster_id: str
    label: str
    narrative: str
    priority_score: float
    matched_accounts: dict[str, float]  # account_name -> YoY %


def _matches_direction(growth: float, direction: str) -> bool:
    if direction == "up":
        return growth > NOTABLE_GROWTH_PCT
    return growth < -NOTABLE_GROWTH_PCT


def _priority_score(matched_growths: list[float], matched_count: int) -> float:
    """Deterministic score, not a fraud/error probability (section 16):
    average magnitude of the matched moves, weighted up by how many
    accounts moved together, capped at 100."""
    avg_magnitude = sum(abs(g) for g in matched_growths) / len(matched_growths)
    score = avg_magnitude * 0.8 + matched_count * 8
    return round(min(score, 100.0), 1)


def _evaluate_directions(
    directions: dict[str, str], year_map: YearMap, latest: int, prior: int
) -> tuple[list[float], dict[str, float]]:
    matched_growths: list[float] = []
    matched_accounts: dict[str, float] = {}
    for code, direction in directions.items():
        growth = growth_rate(year_map, code, latest, prior)
        if growth is None:
            continue
        if _matches_direction(growth, direction):
            matched_growths.append(growth)
            matched_accounts[CANONICAL_ACCOUNT_NAMES.get(code, code)] = growth
    return matched_growths, matched_accounts


def detect_narrative_patterns(year_map: YearMap, latest: int, prior: int) -> list[NarrativePatternHit]:
    hits: list[NarrativePatternHit] = []

    for cluster in CLUSTER_DEFINITIONS:
        matched_growths, matched_accounts = _evaluate_directions(cluster.directions, year_map, latest, prior)
        min_needed = cluster.min_matched

        if len(matched_growths) < min_needed and cluster.fallback_directions:
            fb_growths, fb_accounts = _evaluate_directions(cluster.fallback_directions, year_map, latest, prior)
            if len(fb_growths) >= cluster.fallback_min_matched:
                matched_growths, matched_accounts = fb_growths, fb_accounts
                min_needed = cluster.fallback_min_matched

        if len(matched_growths) >= min_needed:
            hits.append(
                NarrativePatternHit(
                    cluster_id=cluster.cluster_id,
                    label=cluster.label,
                    narrative=cluster.narrative,
                    priority_score=_priority_score(matched_growths, len(matched_growths)),
                    matched_accounts=matched_accounts,
                )
            )

    hits.sort(key=lambda h: h.priority_score, reverse=True)
    return hits
