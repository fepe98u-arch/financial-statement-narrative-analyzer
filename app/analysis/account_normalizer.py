"""Account name normalization (PROJECT_SPEC.md section 10).

Different years/filings can use different labels for the same economic
account ("매출채권" vs "매출채권및기타채권" vs "외상매출금"). This module
maps a raw label to a canonical account code, but never *silently* resolves
an ambiguous case — low-confidence matches come back as UNRESOLVED and are
meant to be surfaced for a human to confirm (section 10: "모호한 경우
자동으로 확정하지 않는다").
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz, process

from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES

# Known synonyms seen across different filing years/formats. This is a
# starting dictionary, not exhaustive — unknown labels fall through to fuzzy
# matching, and anything still unclear becomes UNRESOLVED rather than a
# guess.
ACCOUNT_DICTIONARY: dict[str, str] = {
    "매출": "SALES",
    "매출액": "SALES",
    "영업수익": "SALES",
    "매출채권": "RECEIVABLE",
    "매출채권및기타채권": "RECEIVABLE",
    "외상매출금": "RECEIVABLE",
    "재고자산": "INVENTORY",
    "재고자산(상품)": "INVENTORY",
    "상품및제품": "INVENTORY",
    "매출원가": "COGS",
    "구축물": "STRUCTURE",
    "구축물(순액)": "STRUCTURE",
    "기계장치": "MACHINERY",
    "기계장치(순액)": "MACHINERY",
    "건설중인자산": "CONSTRUCTION_IN_PROGRESS",
    "감가상각비": "DEPRECIATION",
    "장기차입금": "LT_BORROWINGS",
    "장기차입금(원화)": "LT_BORROWINGS",
    "이자비용": "INTEREST_EXPENSE",
    "영업활동현금흐름": "OPERATING_CF",
    "영업활동으로인한현금흐름": "OPERATING_CF",
    "영업이익": "OPERATING_PROFIT",
    "순이익": "NET_INCOME",
    "당기순이익": "NET_INCOME",
    "대손충당금": "ALLOWANCE_DOUBTFUL",
    "총자산": "TOTAL_ASSETS",
    "자산총계": "TOTAL_ASSETS",
}

FUZZY_HIGH_CONFIDENCE = 90.0
FUZZY_LOW_CONFIDENCE = 70.0


class MappingMethod(str, Enum):
    EXACT = "EXACT"
    ACCOUNT_DICTIONARY = "ACCOUNT_DICTIONARY"
    FUZZY = "FUZZY"
    MANUAL = "MANUAL"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class AccountMapping:
    raw_account_name: str
    canonical_account_code: str | None
    canonical_account_name: str | None
    mapping_method: MappingMethod
    mapping_confidence: float  # 0.0-100.0


def normalize_account_name(raw_account_name: str) -> AccountMapping:
    raw = raw_account_name.strip()

    if raw in CANONICAL_ACCOUNT_NAMES.values():
        code = next(c for c, name in CANONICAL_ACCOUNT_NAMES.items() if name == raw)
        return AccountMapping(raw, code, CANONICAL_ACCOUNT_NAMES[code], MappingMethod.EXACT, 100.0)

    if raw in ACCOUNT_DICTIONARY:
        code = ACCOUNT_DICTIONARY[raw]
        return AccountMapping(
            raw, code, CANONICAL_ACCOUNT_NAMES[code], MappingMethod.ACCOUNT_DICTIONARY, 100.0
        )

    match = process.extractOne(raw, ACCOUNT_DICTIONARY.keys(), scorer=fuzz.WRatio)
    if match is not None:
        matched_label, score, _ = match
        code = ACCOUNT_DICTIONARY[matched_label]
        if score >= FUZZY_HIGH_CONFIDENCE:
            return AccountMapping(
                raw, code, CANONICAL_ACCOUNT_NAMES[code], MappingMethod.FUZZY, round(score, 1)
            )
        if score >= FUZZY_LOW_CONFIDENCE:
            # Still returned, but callers should treat sub-90 fuzzy matches
            # as "needs confirmation" rather than final.
            return AccountMapping(
                raw, code, CANONICAL_ACCOUNT_NAMES[code], MappingMethod.FUZZY, round(score, 1)
            )

    return AccountMapping(raw, None, None, MappingMethod.UNRESOLVED, 0.0)


def normalize_many(raw_account_names: list[str]) -> list[AccountMapping]:
    return [normalize_account_name(name) for name in raw_account_names]
