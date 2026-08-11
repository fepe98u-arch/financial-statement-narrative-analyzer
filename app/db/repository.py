"""Persistence layer: turns analysis-engine output into rows, and back.

Every function here takes an Engine explicitly rather than opening a global
connection, so the UI can catch a connection failure and degrade gracefully
instead of crashing the whole app when PostgreSQL isn't running yet.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.analysis.historical_patterns import AccountHistoricalPattern
from app.analysis.investigation_questions import InvestigationQuestionSet
from app.analysis.narrative_patterns import NarrativePatternHit
from app.analysis.relationship_rules import RelationshipRuleHit
from app.db.models import (
    AnalysisRun,
    Base,
    Company,
    DetectedPattern,
    FinancialFact,
    HistoricalPatternRecord,
    HumanReview,
    InvestigationQuestionRecord,
    PatternAccount,
)


class PatternReviewStatus(str, Enum):
    """PROJECT_SPEC.md section 49, pattern-level review options."""

    MEANINGFUL = "유의미함"
    NOT_MEANINGFUL = "유의미하지_않음"
    NEEDS_FURTHER_REVIEW = "추가조사_필요"
    EXPLANATION_CONFIRMED = "설명_확인_완료"
    DEFERRED = "보류"


class EvidenceReviewStatus(str, Enum):
    """PROJECT_SPEC.md section 49, public-evidence-level review options
    (kept here for Phase 6+ reuse even though nothing writes it yet)."""

    RELEVANT = "관련_있음"
    NOT_RELEVANT = "관련_없음"
    POSSIBLE_EXPLANATION = "가능한_설명"
    DIRECT_EVIDENCE = "직접적_근거"


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def check_connection(engine: Engine) -> tuple[bool, str]:
    from app.security_logging import log_event

    try:
        with engine.connect():
            log_event("DB_CONNECTION_CHECK", success=True, provider="postgresql")
            return True, "OK"
    except Exception as exc:  # local connectivity check only, not logged with secrets
        log_event("DB_CONNECTION_CHECK", success=False, provider="postgresql", error_code=type(exc).__name__)
        return False, str(exc)


def get_or_create_company(session: Session, name: str) -> Company:
    company = session.scalar(select(Company).where(Company.name == name))
    if company is None:
        company = Company(name=name)
        session.add(company)
        session.flush()
    return company


def sync_financial_facts(session: Session, company: Company, year_map: dict[str, dict[int, float]], account_names: dict[str, str]) -> None:
    existing = {
        (f.year, f.account_code)
        for f in session.scalars(select(FinancialFact).where(FinancialFact.company_id == company.id))
    }
    for code, year_values in year_map.items():
        for year, amount in year_values.items():
            if (year, code) in existing:
                continue
            session.add(
                FinancialFact(
                    company_id=company.id,
                    year=year,
                    account_code=code,
                    account_name=account_names.get(code, code),
                    amount=amount,
                )
            )


def save_analysis_run(
    engine: Engine,
    company_name: str,
    latest_year: int,
    prior_year: int,
    year_map: dict[str, dict[int, float]],
    account_names: dict[str, str],
    narrative_hits: list[NarrativePatternHit],
    rule_hits: list[RelationshipRuleHit],
    historical_results: list[AccountHistoricalPattern],
    question_sets: list[InvestigationQuestionSet],
) -> int:
    with Session(engine) as session:
        company = get_or_create_company(session, company_name)
        sync_financial_facts(session, company, year_map, account_names)

        run = AnalysisRun(company_id=company.id, latest_year=latest_year, prior_year=prior_year)
        session.add(run)
        session.flush()

        for hit in narrative_hits:
            pattern = DetectedPattern(
                analysis_run_id=run.id,
                pattern_type="NARRATIVE_CLUSTER",
                pattern_key=hit.cluster_id,
                label=hit.label,
                narrative_or_description=hit.narrative,
                priority_score=hit.priority_score,
            )
            session.add(pattern)
            session.flush()
            for account_name, yoy in hit.matched_accounts.items():
                session.add(
                    PatternAccount(
                        detected_pattern_id=pattern.id,
                        account_code=account_name,
                        account_name=account_name,
                        yoy_pct=yoy,
                    )
                )

        for hit in rule_hits:
            pattern = DetectedPattern(
                analysis_run_id=run.id,
                pattern_type="RELATIONSHIP_RULE",
                pattern_key=hit.rule_id,
                label=hit.label,
                narrative_or_description=hit.description,
                priority_score=None,
            )
            session.add(pattern)
            session.flush()
            for account_name, yoy in hit.evidence.items():
                session.add(
                    PatternAccount(
                        detected_pattern_id=pattern.id,
                        account_code=account_name,
                        account_name=account_name,
                        yoy_pct=yoy,
                    )
                )

        for result in historical_results:
            session.add(
                HistoricalPatternRecord(
                    analysis_run_id=run.id,
                    account_code=result.account_code,
                    account_name=result.account_name,
                    current_growth=result.current_growth,
                    classification=result.classification.value,
                )
            )

        for qs in question_sets:
            for question in qs.questions:
                session.add(
                    InvestigationQuestionRecord(
                        analysis_run_id=run.id,
                        source_type=qs.source_type,
                        source_id=qs.source_id,
                        source_label=qs.source_label,
                        question_text=question,
                    )
                )

        session.commit()
        return run.id


def save_human_review(engine: Engine, target_type: str, target_id: str, status: str, note: str | None = None) -> None:
    with Session(engine) as session:
        session.add(
            HumanReview(
                target_type=target_type,
                target_id=target_id,
                status=status,
                note=note,
                reviewed_at=dt.datetime.now(dt.UTC).replace(tzinfo=None),
            )
        )
        session.commit()


def get_latest_human_reviews(engine: Engine, target_type: str) -> dict[str, HumanReview]:
    """Latest review per target_id, most recent first."""
    with Session(engine) as session:
        rows = session.scalars(
            select(HumanReview)
            .where(HumanReview.target_type == target_type)
            .order_by(HumanReview.reviewed_at.desc())
        ).all()
        latest: dict[str, HumanReview] = {}
        for row in rows:
            latest.setdefault(row.target_id, row)
        return latest
