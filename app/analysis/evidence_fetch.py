"""Shared "fetch real articles + locally rank them per detected pattern"
flow, used by both the Public Data and Evidence Analysis pages so this
logic (keyword variants, date filtering, cross-pattern dedup) can't quietly
drift apart between the two.

Performs real network I/O via NaverNewsProvider — only call this after
consent has been obtained and from a direct user action (a button click),
never from a page's plain re-render path.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.evidence_ranking import EvidenceMatch, documents_from_provider_results, rank_public_evidence
from app.analysis.investigation_questions import (
    InvestigationQuestionSet,
    search_keywords_for,
    topic_keywords_for,
)
from app.analysis.narrative_patterns import NarrativePatternHit
from app.analysis.relationship_rules import RelationshipRuleHit
from app.public_data_collector.news_provider import NaverNewsProvider, coverage_message, filter_by_date_range
from app.public_data_collector.schemas import PublicCollectionRequest

# Each pattern's own keyword variants are tried as SEPARATE queries and
# merged (see search_keywords_for's docstring) — capped here so a pattern
# with many variants doesn't balloon into dozens of HTTP calls per click.
MAX_KEYWORD_VARIANTS = 3
# Reduced from NaverNewsProvider's own default (10) since each variant
# query is already narrow; keeps total calls per pattern reasonable even
# with multiple variants.
VARIANT_MAX_PAGES = 3


@dataclass(frozen=True)
class PatternEvidence:
    question_set: InvestigationQuestionSet
    evidence: dict[str, float]  # the actual detected growth rates, e.g. {"지분법손익증가율": -96.1}
    matches: list[EvidenceMatch]
    coverage_lines: list[str] = field(default_factory=list)


def evidence_lookup_for_hits(
    narrative_hits: list[NarrativePatternHit], rule_hits: list[RelationshipRuleHit]
) -> dict[tuple[str, str], dict[str, float]]:
    lookup: dict[tuple[str, str], dict[str, float]] = {}
    for hit in narrative_hits:
        lookup[("NARRATIVE_PATTERN", hit.cluster_id)] = hit.matched_accounts
    for hit in rule_hits:
        lookup[("RELATIONSHIP_RULE", hit.rule_id)] = hit.evidence
    return lookup


def fetch_articles_for_pattern(
    company: str, source_type: str, source_id: str, date_from: str, date_to: str
) -> tuple[list[dict], list[str]]:
    """Fetches real articles for ONE pattern: one query per keyword variant
    (search_keywords_for), merged and deduped, then filtered to only what's
    actually published within [date_from, date_to] (Naver's own date_from/
    date_to aren't a real filter — see filter_by_date_range) AND whose
    TITLE names the company itself.

    That second filter matters because Naver's search does loose,
    group-wide matching, not exact-phrase (confirmed empirically — quoting
    the company name in the query made no difference): most results for
    e.g. "LG에너지솔루션" only mention it in passing within a story mainly
    about a different group affiliate (LG전자, LG디스플레이, ...) or the
    group as a whole. Requiring the company's own name in the title is the
    only mechanically reliable signal that an article is actually about
    that company rather than just co-mentioning it — confirmed on real
    keyword-narrowed queries to keep a real, useful fraction (2-17%,
    articles like "LG에너지솔루션, 2분기 영업익 1133억…전년비 77%↓"), unlike
    a bare company-name-only query where this dropped to ~1%. Returns the
    filtered raw provider dicts plus one coverage line per variant query."""
    keywords = search_keywords_for(source_type, source_id)[:MAX_KEYWORD_VARIANTS]
    variant_queries = keywords or [None]

    merged: dict[str, dict] = {}
    coverage_lines: list[str] = []
    for keyword in variant_queries:
        request = PublicCollectionRequest(
            public_company_name=company,
            date_from=date_from,
            date_to=date_to,
            page=1,
            page_size=100,
            topic_keyword=keyword,
        )
        raw_results = NaverNewsProvider().fetch_many(request, max_pages=VARIANT_MAX_PAGES)
        for r in raw_results:
            key = r.get("public_document_id") or r.get("url") or r.get("title")
            merged.setdefault(key, r)
        search_desc = f"'{company} {keyword}'" if keyword else f"'{company}'"
        coverage_lines.append(f"{search_desc}: {coverage_message(raw_results, date_from)}")

    in_range = filter_by_date_range(list(merged.values()), date_from, date_to)
    on_topic = [r for r in in_range if company in r.get("title", "")]
    coverage_lines.append(
        f"제목에 '{company}'가 포함된 기사만 사용: {len(on_topic)}건 (날짜 범위 내 {len(in_range)}건 중)"
    )
    return on_topic, coverage_lines


def fetch_and_rank_evidence(
    company: str,
    question_sets: list[InvestigationQuestionSet],
    narrative_hits: list[NarrativePatternHit],
    rule_hits: list[RelationshipRuleHit],
    model,
    date_from: str,
    date_to: str,
    top_k: int = 3,
    max_patterns: int = 2,
) -> list[PatternEvidence]:
    """For each of the top `max_patterns` detected patterns: fetch real
    articles (fetch_articles_for_pattern) then rank locally against that
    pattern's investigation question. An article already claimed by an
    earlier (higher-priority) pattern in this call is excluded from later
    ones, so the same article isn't shown twice."""
    evidence_lookup = evidence_lookup_for_hits(narrative_hits, rule_hits)
    claimed_document_ids: set[str] = set()
    results: list[PatternEvidence] = []

    for qs in question_sets[:max_patterns]:
        question = qs.questions[0]
        in_range, coverage_lines = fetch_articles_for_pattern(
            company, qs.source_type, qs.source_id, date_from, date_to
        )
        documents = documents_from_provider_results(in_range)

        local_keywords = topic_keywords_for(qs.source_type, qs.source_id)
        unclaimed = [d for d in documents if d.public_document_id not in claimed_document_ids]
        matches = rank_public_evidence(model, question, unclaimed, top_k=top_k, topic_keywords=local_keywords)
        for m in matches:
            claimed_document_ids.add(m.document_id)

        results.append(
            PatternEvidence(
                question_set=qs,
                evidence=evidence_lookup.get((qs.source_type, qs.source_id), {}),
                matches=matches,
                coverage_lines=coverage_lines,
            )
        )

    return results
