"""Guards on search_keyword_for()'s vocabulary (CLAUDE.md / PROJECT_SPEC.md
section 25's owner-approved 2026-08-17 exception): every value must be a
bare account-name-level term, never a direction, number, or judgment word —
those are exactly what makes a search term reveal what the pattern engine
concluded rather than just what it's curious about.
"""
from __future__ import annotations

from app.analysis.investigation_questions import (
    NARRATIVE_SEARCH_KEYWORDS,
    RULE_SEARCH_KEYWORDS,
    search_keywords_for,
)

# Substrings that would turn a bare account name into a directional/judgment
# claim if they ever crept into a search-keyword value.
_FORBIDDEN_SUBSTRINGS = (
    "증가", "감소", "상승", "하락", "급증", "급감", "둔화", "지연", "부진",
    "위험", "우려", "손실", "리스크", "확대", "축소",
)


def test_search_keywords_contain_no_directional_or_judgment_words():
    all_keyword_lists = {**NARRATIVE_SEARCH_KEYWORDS, **RULE_SEARCH_KEYWORDS}
    for source_id, keywords in all_keyword_lists.items():
        for keyword in keywords:
            for forbidden in _FORBIDDEN_SUBSTRINGS:
                assert forbidden not in keyword, (
                    f"{source_id}'s search keyword {keyword!r} contains {forbidden!r} — "
                    "search_keywords_for() values must be bare account names only"
                )


def test_search_keywords_for_rule_returns_expected_variants():
    assert search_keywords_for("RELATIONSHIP_RULE", "BORROWINGS_UP_INTEREST_FLAT") == ["이자비용", "금융비용"]


def test_search_keywords_for_narrative_returns_expected_variants():
    assert search_keywords_for("NARRATIVE_PATTERN", "CREDIT_RISK") == ["대손충당금"]


def test_search_keywords_for_unknown_source_returns_empty_list():
    assert search_keywords_for("RELATIONSHIP_RULE", "SOME_FUTURE_RULE_WITH_NO_ENTRY_YET") == []
