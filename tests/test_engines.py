from app.analysis.metrics_engine import compute_all_metrics, dso, growth_rate
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import load_financial_facts, to_year_map

LATEST, PRIOR = 2026, 2025


def test_abc_manufacturing_capex_financing_growth_rates_match_spec_example():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")

    # These mirror PROJECT_SPEC.md section 47's PATTERN 01 example almost
    # exactly by construction (see app/data/synthetic.py docstring).
    assert growth_rate(year_map, "INVENTORY", LATEST, PRIOR) == -38.0
    assert growth_rate(year_map, "STRUCTURE", LATEST, PRIOR) == 81.8
    assert growth_rate(year_map, "MACHINERY", LATEST, PRIOR) == 51.1
    assert growth_rate(year_map, "LT_BORROWINGS", LATEST, PRIOR) == 70.0


def test_abc_manufacturing_triggers_capex_up_depreciation_flat_rule():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")
    hits = {hit.rule_id for hit in detect_relationship_rules(year_map, LATEST, PRIOR)}
    assert "CAPEX_UP_DEPRECIATION_FLAT" in hits
    assert "BORROWINGS_UP_INTEREST_FLAT" in hits


def test_operating_profit_up_net_income_down_rule_fires_on_divergence():
    # Found via real LG Energy Solution data: 영업이익 +134% while 순이익
    # -76% in the same year — a real, sizeable divergence no existing rule
    # caught until this one was added.
    year_map = {
        "OPERATING_PROFIT": {2024: 575_387, 2025: 1_346_120},
        "NET_INCOME": {2024: 338_602, 2025: 80_803},
    }
    hits = {hit.rule_id for hit in detect_relationship_rules(year_map, 2025, 2024)}
    assert "OPERATING_PROFIT_UP_NET_INCOME_DOWN" in hits


def test_operating_profit_up_net_income_down_rule_silent_when_both_rise():
    year_map = {
        "OPERATING_PROFIT": {2024: 100, 2025: 110},
        "NET_INCOME": {2024: 100, 2025: 120},
    }
    hits = {hit.rule_id for hit in detect_relationship_rules(year_map, 2025, 2024)}
    assert "OPERATING_PROFIT_UP_NET_INCOME_DOWN" not in hits


def test_abc_manufacturing_triggers_production_expansion_narrative_pattern():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "ABC Manufacturing")
    patterns = {hit.cluster_id for hit in detect_narrative_patterns(year_map, LATEST, PRIOR)}
    assert "PRODUCTION_EXPANSION" in patterns
    assert "CAPEX_FINANCING" in patterns


def test_sample_electronics_triggers_revenue_receivable_and_credit_risk():
    facts = load_financial_facts()
    year_map = to_year_map(facts, "Sample Electronics")

    rule_hits = {hit.rule_id for hit in detect_relationship_rules(year_map, LATEST, PRIOR)}
    assert "SALES_DOWN_RECEIVABLE_UP" in rule_hits
    assert "NET_INCOME_UP_OCF_DOWN" in rule_hits

    pattern_hits = {hit.cluster_id for hit in detect_narrative_patterns(year_map, LATEST, PRIOR)}
    assert "CREDIT_RISK" in pattern_hits


def test_metrics_never_fabricate_missing_inputs():
    facts = load_financial_facts()
    # Sample Electronics has no STRUCTURE/MACHINERY/borrowings data, so
    # CAPEX-related metrics must simply be absent, not zero or guessed.
    year_map = to_year_map(facts, "Sample Electronics")
    metrics = {m.key for m in compute_all_metrics(year_map, LATEST, PRIOR)}
    assert "CAPEX_GROWTH" not in metrics
    assert "LT_BORROWINGS_GROWTH" not in metrics


def test_dso_is_none_when_inputs_missing():
    assert dso({}, 2026) is None
