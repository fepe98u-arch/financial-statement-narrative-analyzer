from app.analysis.historical_patterns import HistoricalClassification, classify_account_history
from app.analysis.investigation_questions import generate_investigation_questions
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.pattern_similarity import compute_pattern_similarity, most_similar_historical_year
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import account_name_map, load_financial_facts, to_year_map

YEARS = [2022, 2023, 2024, 2025, 2026]


def test_abc_inventory_and_structure_are_intensified_vs_own_history():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")

    inventory = classify_account_history(year_map, "INVENTORY", "재고자산", YEARS)
    structure = classify_account_history(year_map, "STRUCTURE", "구축물", YEARS)

    assert inventory.classification == HistoricalClassification.INTENSIFIED_PATTERN
    assert structure.classification == HistoricalClassification.INTENSIFIED_PATTERN


def test_reversal_pattern_detected_when_direction_flips():
    # Hand-built series: notable growth in year 2025, then a notable decline
    # in 2026 — direction flips, so this must not be called INTENSIFIED or
    # RECURRING.
    year_map = {"X": {2022: 100, 2023: 101, 2024: 102, 2025: 140, 2026: 100}}
    result = classify_account_history(year_map, "X", "테스트계정", YEARS)
    assert result.classification == HistoricalClassification.REVERSAL_PATTERN


def test_flat_series_is_normal_range():
    year_map = {"X": {2022: 100, 2023: 101, 2024: 102, 2025: 103, 2026: 104}}
    result = classify_account_history(year_map, "X", "테스트계정", YEARS)
    assert result.classification == HistoricalClassification.NORMAL_RANGE


def test_pattern_similarity_is_symmetric_formula_not_ai_invented():
    current = {"A": 50.0, "B": -20.0}
    identical = {"A": 50.0, "B": -20.0}
    similarity = compute_pattern_similarity(current, identical)
    assert similarity.direction_similarity_pct == 100.0
    assert similarity.magnitude_similarity_pct == 100.0

    opposite = {"A": -50.0, "B": 20.0}
    similarity_opposite = compute_pattern_similarity(current, opposite)
    assert similarity_opposite.direction_similarity_pct == 0.0


def test_most_similar_historical_year_is_found_for_abc_capex_cluster():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")
    result = most_similar_historical_year(year_map, ["STRUCTURE", "MACHINERY", "LT_BORROWINGS"], YEARS)
    assert result is not None
    year, similarity = result
    assert year in YEARS[1:-1]
    assert similarity.direction_similarity_pct == 100.0  # all three grew every year


def test_investigation_questions_are_generated_from_local_patterns_only():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")
    narrative_hits = detect_narrative_patterns(year_map, 2026, 2025)
    rule_hits = detect_relationship_rules(year_map, 2026, 2025)

    question_sets = generate_investigation_questions(narrative_hits, rule_hits)
    assert question_sets
    all_questions = [q for qs in question_sets for q in qs.questions]
    assert any("확장" in q or "투자" in q for q in all_questions)
