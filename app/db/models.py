"""SQLAlchemy models for the subset of PROJECT_SPEC.md section 40's table
list that Phases 1-4 actually need. Later phases (public_documents,
document_chunks, retrieval_hits, public_collection_runs, security_events,
model_configs) get their tables added when those phases are built, not
before — see CLAUDE.md "build in phases, don't jump ahead".
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    financial_facts: Mapped[list["FinancialFact"]] = relationship(back_populates="company")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="company")


class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (UniqueConstraint("company_id", "year", "account_code", name="uq_fact_company_year_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="KRW_MILLION")

    company: Mapped[Company] = relationship(back_populates="financial_facts")


class AccountMappingRecord(Base):
    __tablename__ = "account_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_account_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mapping_method: Mapped[str] = mapped_column(String(32), nullable=False)
    mapping_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    latest_year: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_year: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    company: Mapped[Company] = relationship(back_populates="analysis_runs")
    detected_patterns: Mapped[list["DetectedPattern"]] = relationship(back_populates="analysis_run")
    historical_patterns: Mapped[list["HistoricalPatternRecord"]] = relationship(back_populates="analysis_run")
    investigation_questions: Mapped[list["InvestigationQuestionRecord"]] = relationship(
        back_populates="analysis_run"
    )


class DetectedPattern(Base):
    """One row per Relationship Rule hit or Narrative Pattern cluster hit."""

    __tablename__ = "detected_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(32), nullable=False)  # RELATIONSHIP_RULE | NARRATIVE_CLUSTER
    pattern_key: Mapped[str] = mapped_column(String(64), nullable=False)  # rule_id or cluster_id
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    narrative_or_description: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="detected_patterns")
    pattern_accounts: Mapped[list["PatternAccount"]] = relationship(back_populates="detected_pattern")


class PatternAccount(Base):
    __tablename__ = "pattern_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    detected_pattern_id: Mapped[int] = mapped_column(ForeignKey("detected_patterns.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    yoy_pct: Mapped[float] = mapped_column(Float, nullable=False)

    detected_pattern: Mapped[DetectedPattern] = relationship(back_populates="pattern_accounts")


class HistoricalPatternRecord(Base):
    __tablename__ = "historical_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    current_growth: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="historical_patterns")


class InvestigationQuestionRecord(Base):
    __tablename__ = "investigation_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str] = mapped_column(String(200), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="investigation_questions")


class HumanReview(Base):
    """Human-in-the-loop status for a pattern or a piece of public evidence
    (PROJECT_SPEC.md section 49). target_id is stored as text so this one
    table can reference either detected_patterns.id (int) now or
    retrieval_hits.id (a later phase) without a schema change."""

    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)  # DETECTED_PATTERN | PUBLIC_EVIDENCE
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
