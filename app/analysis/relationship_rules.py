"""Relationship Rule Engine (PROJECT_SPEC.md section 13).

Detects fairly direct account-to-account relationships worth a second look.
Per the spec, a hit here is never called an "error" — it's an
"Attention Pattern" that a human reviewer should look at, nothing more.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.metrics_engine import YearMap, growth_rate

# A YoY move below this is treated as noise, not a signal, for every rule
# below.
NOTABLE_GROWTH_PCT = 5.0
# How many percentage points faster one account must grow than another to
# count as "훨씬 더 빠르게" (much faster). Tuned down from 10 after real
# Yuhan Corp data (매출 +5.7%, 매출채권 +14.0% — a 8.3pp gap) showed 10pp
# was too conservative to flag a receivables-growing-faster-than-sales case
# worth a reviewer's attention.
FASTER_MARGIN_PP = 5.0
# A companion account (depreciation, interest) growing at less than this
# fraction of the driving account's growth counts as "변화가 미미함/작음".
SMALL_CHANGE_FRACTION = 1.0 / 3.0
# The driving account (fixed assets, borrowings) must itself grow at least
# this much before the "companion barely moved" comparison is meaningful.
MIN_DRIVING_GROWTH_PCT = 20.0


@dataclass(frozen=True)
class RelationshipRuleHit:
    rule_id: str
    label: str  # always "Attention Pattern" per PROJECT_SPEC.md section 13
    description: str
    evidence: dict[str, float] = field(default_factory=dict)


def _g(year_map: YearMap, code: str, latest: int, prior: int) -> float | None:
    return growth_rate(year_map, code, latest, prior)


def _rule_sales_down_receivable_up(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    sales_g, recv_g = _g(year_map, "SALES", latest, prior), _g(year_map, "RECEIVABLE", latest, prior)
    if sales_g is None or recv_g is None:
        return None
    if sales_g < -NOTABLE_GROWTH_PCT and recv_g > NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "SALES_DOWN_RECEIVABLE_UP",
            "Attention Pattern",
            "매출이 감소했는데 매출채권이 증가했습니다. 회수 지연이나 매출 인식 방식 변화 등 추가 확인이 필요할 수 있습니다.",
            {"매출증가율": sales_g, "매출채권증가율": recv_g},
        )
    return None


def _rule_sales_down_inventory_up(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    sales_g, inv_g = _g(year_map, "SALES", latest, prior), _g(year_map, "INVENTORY", latest, prior)
    if sales_g is None or inv_g is None:
        return None
    if sales_g < -NOTABLE_GROWTH_PCT and inv_g > NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "SALES_DOWN_INVENTORY_UP",
            "Attention Pattern",
            "매출이 감소했는데 재고자산이 증가했습니다. 수요 둔화 대비 생산 조정 여부를 확인할 필요가 있을 수 있습니다.",
            {"매출증가율": sales_g, "재고증가율": inv_g},
        )
    return None


def _rule_netincome_up_ocf_down(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    ni_g, ocf_g = _g(year_map, "NET_INCOME", latest, prior), _g(year_map, "OPERATING_CF", latest, prior)
    if ni_g is None or ocf_g is None:
        return None
    if ni_g > NOTABLE_GROWTH_PCT and ocf_g < -NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "NET_INCOME_UP_OCF_DOWN",
            "Attention Pattern",
            "순이익은 증가했는데 영업활동현금흐름은 감소했습니다. 이익의 질(손익-현금 괴리) 확인이 필요할 수 있습니다.",
            {"순이익증가율": ni_g, "영업CF증가율": ocf_g},
        )
    return None


def _rule_operating_profit_up_net_income_down(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    op_g, ni_g = _g(year_map, "OPERATING_PROFIT", latest, prior), _g(year_map, "NET_INCOME", latest, prior)
    if op_g is None or ni_g is None:
        return None
    if op_g > NOTABLE_GROWTH_PCT and ni_g < -NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "OPERATING_PROFIT_UP_NET_INCOME_DOWN",
            "Attention Pattern",
            "영업이익은 증가했는데 순이익은 감소했습니다. 영업외손익(금융비용, 지분법손익, 일회성 손실 등)에서 "
            "큰 변화가 있었는지 확인이 필요할 수 있습니다.",
            {"영업이익증가율": op_g, "순이익증가율": ni_g},
        )
    return None


def _rule_sales_up_receivable_up_faster(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    sales_g, recv_g = _g(year_map, "SALES", latest, prior), _g(year_map, "RECEIVABLE", latest, prior)
    if sales_g is None or recv_g is None:
        return None
    if sales_g > NOTABLE_GROWTH_PCT and recv_g > sales_g + FASTER_MARGIN_PP:
        return RelationshipRuleHit(
            "SALES_UP_RECEIVABLE_UP_FASTER",
            "Attention Pattern",
            "매출채권이 매출보다 훨씬 빠르게 증가했습니다. 매출 인식 시점이나 채권 회수 정책 변화를 확인할 필요가 있을 수 있습니다.",
            {"매출증가율": sales_g, "매출채권증가율": recv_g},
        )
    return None


def _rule_sales_up_inventory_up_faster(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    sales_g, inv_g = _g(year_map, "SALES", latest, prior), _g(year_map, "INVENTORY", latest, prior)
    if sales_g is None or inv_g is None:
        return None
    if sales_g > NOTABLE_GROWTH_PCT and inv_g > sales_g + FASTER_MARGIN_PP:
        return RelationshipRuleHit(
            "SALES_UP_INVENTORY_UP_FASTER",
            "Attention Pattern",
            "재고자산이 매출보다 훨씬 빠르게 증가했습니다. 과잉 생산이나 수요 예측 변화 등을 확인할 필요가 있을 수 있습니다.",
            {"매출증가율": sales_g, "재고증가율": inv_g},
        )
    return None


def _rule_capex_up_depreciation_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    capex_growth = [_g(year_map, code, latest, prior) for code in ("STRUCTURE", "MACHINERY")]
    capex_growth = [v for v in capex_growth if v is not None]
    dep_g = _g(year_map, "DEPRECIATION", latest, prior)
    if not capex_growth or dep_g is None:
        return None
    avg_capex_g = sum(capex_growth) / len(capex_growth)
    if avg_capex_g > MIN_DRIVING_GROWTH_PCT and dep_g < avg_capex_g * SMALL_CHANGE_FRACTION:
        return RelationshipRuleHit(
            "CAPEX_UP_DEPRECIATION_FLAT",
            "Attention Pattern",
            "유형자산이 크게 증가했는데 감가상각비 변화는 상대적으로 작습니다. 신규 자산의 가동 개시 시점이나 감가상각 정책을 확인할 필요가 있을 수 있습니다.",
            {"유형자산증가율(평균)": round(avg_capex_g, 1), "감가상각비증가율": dep_g},
        )
    return None


def _rule_borrowings_up_interest_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    borrow_g = _g(year_map, "LT_BORROWINGS", latest, prior)
    interest_g = _g(year_map, "INTEREST_EXPENSE", latest, prior)
    if borrow_g is None or interest_g is None:
        return None
    if borrow_g > MIN_DRIVING_GROWTH_PCT and interest_g < borrow_g * SMALL_CHANGE_FRACTION:
        return RelationshipRuleHit(
            "BORROWINGS_UP_INTEREST_FLAT",
            "Attention Pattern",
            "장기차입금이 크게 증가했는데 이자비용 변화는 미미합니다. 차입 시점(기중 vs 기말)이나 금리 조건을 확인할 필요가 있을 수 있습니다.",
            {"차입금증가율": borrow_g, "이자비용증가율": interest_g},
        )
    return None


_ALL_RULES = (
    _rule_sales_down_receivable_up,
    _rule_sales_down_inventory_up,
    _rule_netincome_up_ocf_down,
    _rule_operating_profit_up_net_income_down,
    _rule_sales_up_receivable_up_faster,
    _rule_sales_up_inventory_up_faster,
    _rule_capex_up_depreciation_flat,
    _rule_borrowings_up_interest_flat,
)


def detect_relationship_rules(year_map: YearMap, latest: int, prior: int) -> list[RelationshipRuleHit]:
    hits = (rule(year_map, latest, prior) for rule in _ALL_RULES)
    return [hit for hit in hits if hit is not None]
