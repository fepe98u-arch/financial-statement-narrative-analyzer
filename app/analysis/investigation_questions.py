"""Investigation Question Engine (PROJECT_SPEC.md section 19).

Generates candidate questions from *local* pattern-engine output using
fixed templates — no LLM call, no network call, nothing invented at
runtime. These questions are PRIVATE DATA: PROJECT_SPEC.md section 19 is
explicit that they must never be sent to Google/Naver/news APIs/DART/any
external LLM. Nothing in this module performs I/O of any kind, which is
what keeps that guarantee true by construction rather than by promise.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.narrative_patterns import NarrativePatternHit
from app.analysis.relationship_rules import RelationshipRuleHit

# cluster_id -> candidate questions, adapted from the section 19 example.
NARRATIVE_QUESTION_TEMPLATES: dict[str, list[str]] = {
    "PRODUCTION_EXPANSION": [
        "생산시설 또는 사업 확장이 있었는가?",
        "신규 설비투자가 있었는가?",
        "대규모 CAPEX 계획이 존재하는가?",
        "생산능력 변화가 있었는가?",
    ],
    "CAPEX_FINANCING": [
        "신규 차입이 투자활동과 관련되는가?",
        "설비투자 자금조달 계획이 있었는가?",
        "차입 조건(금리, 만기)에 변화가 있었는가?",
    ],
    "REVENUE_RECEIVABLE": [
        "매출 인식 기준 변경이 있었는가?",
        "주요 거래처의 결제 조건이 변경되었는가?",
        "매출 감소에도 매출채권이 증가한 사업적 이유가 있는가?",
    ],
    "CREDIT_RISK": [
        "특정 거래처의 신용위험이 증가했는가?",
        "대손충당금 설정 정책이 변경되었는가?",
        "매출채권 회수 지연이 발생했는가?",
    ],
    "PROFIT_CASHFLOW": [
        "손익과 현금흐름 간 괴리의 원인은 무엇인가?",
        "비현금성 손익 항목이 있었는가?",
        "운전자본 변동이 현금흐름에 큰 영향을 미쳤는가?",
    ],
}

# rule_id -> candidate questions.
RULE_QUESTION_TEMPLATES: dict[str, list[str]] = {
    "SALES_DOWN_RECEIVABLE_UP": ["매출 감소 중 매출채권이 증가한 원인은 무엇인가?"],
    "SALES_DOWN_INVENTORY_UP": ["수요 둔화 대비 생산/구매 조정이 있었는가?"],
    "NET_INCOME_UP_OCF_DOWN": ["순이익과 영업현금흐름의 괴리 원인은 무엇인가?"],
    "OPERATING_PROFIT_UP_NET_INCOME_DOWN": [
        "영업외손익(금융비용, 지분법손익, 외환손익 등)에 일회성 항목이 있었는가?",
        "이자비용이나 환율 변동이 순이익에 큰 영향을 미쳤는가?",
    ],
    "SALES_UP_RECEIVABLE_UP_FASTER": ["매출채권이 매출보다 빠르게 증가한 이유는 무엇인가?"],
    "SALES_UP_INVENTORY_UP_FASTER": ["재고가 매출보다 빠르게 증가한 이유는 무엇인가?"],
    "CAPEX_UP_DEPRECIATION_FLAT": ["신규 유형자산의 가동 개시 시점은 언제인가?"],
    "BORROWINGS_UP_INTEREST_FLAT": ["신규 차입 시점과 금리 조건은 어떠한가?"],
}

# source_id -> keywords that must appear (substring match) somewhere in a
# candidate article for it to even be considered a semantic-ranking
# candidate for that question. The local embedding model alone isn't
# reliable enough to separate topically-relevant articles from articles
# that just share generic finance/stock-market vocabulary with the company
# name (e.g. a short-selling-balance article scored HIGHER against the
# "일회성 영업외손익" question than an article actually about 지분법손실) —
# this keyword gate is the first filter; embedding similarity only ranks
# within whatever passes it.
NARRATIVE_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "PRODUCTION_EXPANSION": ["증설", "생산라인", "설비투자", "공장 착공", "생산능력", "capex", "CAPEX"],
    "CAPEX_FINANCING": ["차입", "자금조달", "회사채", "유상증자", "시설자금"],
    "REVENUE_RECEIVABLE": ["매출채권", "매출 인식", "결제 조건", "외상매출금"],
    "CREDIT_RISK": ["대손충당금", "신용위험", "채권 회수", "연체", "부실채권"],
    "PROFIT_CASHFLOW": ["영업현금흐름", "비현금성", "운전자본", "감가상각"],
}

RULE_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "SALES_DOWN_RECEIVABLE_UP": ["매출채권", "결제 지연", "외상매출금"],
    "SALES_DOWN_INVENTORY_UP": ["재고", "재고자산", "수요 둔화", "생산 조정"],
    "NET_INCOME_UP_OCF_DOWN": ["영업현금흐름", "비현금성", "운전자본"],
    "OPERATING_PROFIT_UP_NET_INCOME_DOWN": [
        "영업외손익", "영업외비용", "금융비용", "지분법", "환율", "외화환산", "일회성", "이자비용",
    ],
    "SALES_UP_RECEIVABLE_UP_FASTER": ["매출채권", "회수기간", "결제조건"],
    "SALES_UP_INVENTORY_UP_FASTER": ["재고자산", "재고 증가", "판매 부진"],
    "CAPEX_UP_DEPRECIATION_FLAT": ["가동", "준공", "시운전", "유형자산 취득"],
    "BORROWINGS_UP_INTEREST_FLAT": ["차입금", "이자율", "차입 조건", "금리"],
}


def topic_keywords_for(source_type: str, source_id: str) -> list[str]:
    if source_type == "NARRATIVE_PATTERN":
        return NARRATIVE_TOPIC_KEYWORDS.get(source_id, [])
    return RULE_TOPIC_KEYWORDS.get(source_id, [])


@dataclass(frozen=True)
class InvestigationQuestionSet:
    source_type: str  # "NARRATIVE_PATTERN" | "RELATIONSHIP_RULE"
    source_id: str
    source_label: str
    questions: list[str]


def generate_investigation_questions(
    narrative_hits: list[NarrativePatternHit], rule_hits: list[RelationshipRuleHit]
) -> list[InvestigationQuestionSet]:
    results: list[InvestigationQuestionSet] = []

    for hit in narrative_hits:
        questions = NARRATIVE_QUESTION_TEMPLATES.get(hit.cluster_id)
        if questions:
            results.append(InvestigationQuestionSet("NARRATIVE_PATTERN", hit.cluster_id, hit.label, questions))

    for hit in rule_hits:
        questions = RULE_QUESTION_TEMPLATES.get(hit.rule_id)
        if questions:
            results.append(InvestigationQuestionSet("RELATIONSHIP_RULE", hit.rule_id, hit.label, questions))

    return results
