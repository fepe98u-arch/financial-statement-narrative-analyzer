import pytest

from app.analysis.historical_patterns import classify_all_accounts
from app.analysis.investigation_questions import generate_investigation_questions
from app.analysis.narrative_patterns import detect_narrative_patterns
from app.analysis.relationship_rules import detect_relationship_rules
from app.data.loader import account_name_map, load_financial_facts, to_year_map
from app.db.connection import CloudDatabaseNotAllowedError, build_engine
from app.db.repository import check_connection

YEARS = [2022, 2023, 2024, 2025, 2026]


def test_cloud_database_url_is_rejected_without_needing_a_live_server():
    with pytest.raises(CloudDatabaseNotAllowedError):
        build_engine("postgresql+psycopg://user:pw@some-cloud-host.example.com:5432/db")


def _live_engine_or_skip():
    try:
        engine = build_engine()
    except CloudDatabaseNotAllowedError as exc:
        pytest.skip(f"DATABASE_URL misconfigured: {exc}")
    ok, message = check_connection(engine)
    if not ok:
        pytest.skip(f"No local PostgreSQL reachable yet — see SETUP_POSTGRESQL.md ({message})")
    return engine


def test_full_round_trip_against_a_live_local_postgres():
    from app.db.repository import get_latest_human_reviews, init_schema, save_analysis_run, save_human_review

    engine = _live_engine_or_skip()
    init_schema(engine)

    facts = load_financial_facts()
    company = "ABC Manufacturing"
    year_map = to_year_map(facts, company)
    names = account_name_map(facts, company)
    latest, prior = YEARS[-1], YEARS[-2]

    narrative_hits = detect_narrative_patterns(year_map, latest, prior)
    rule_hits = detect_relationship_rules(year_map, latest, prior)
    historical_results = classify_all_accounts(year_map, names, YEARS)
    question_sets = generate_investigation_questions(narrative_hits, rule_hits)

    run_id = save_analysis_run(
        engine, company, latest, prior, year_map, names,
        narrative_hits, rule_hits, historical_results, question_sets,
    )
    assert run_id > 0

    target_id = f"{company}:NARRATIVE_CLUSTER:CAPEX_FINANCING"
    save_human_review(engine, "DETECTED_PATTERN", target_id, "추가조사_필요", "테스트 노트")
    reviews = get_latest_human_reviews(engine, "DETECTED_PATTERN")
    assert reviews[target_id].status == "추가조사_필요"
