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
# A companion account counts as "안정적/정체" when its own YoY move is
# below this, independent of any driving account (used where there's no
# natural "grew at least X% of the driver" relationship to lean on — e.g.
# pretax income being flat while tax expense swings).
FLAT_ABS_THRESHOLD_PCT = 10.0
# How many percentage points a gross margin ((매출-매출원가)/매출) must
# drop for rising sales alongside a shrinking margin to be worth a look.
MARGIN_DROP_THRESHOLD_PP = 3.0
# 이익잉여금's YoY dollar increase relative to the same year's 순이익 — at
# or above this fraction, retained earnings absorbed essentially all of net
# income, i.e. no material dividend/capital outflow this year.
NO_DIVIDEND_RATIO_THRESHOLD = 0.9
# 기타포괄손익's YoY dollar swing, sized against that year's 순이익 (as a
# base for materiality — OCI swings between small positive/negative values
# make a plain %-growth comparison meaningless whenever the prior value is
# near zero or flips sign).
OCI_MATERIALITY_RATIO_PCT = 30.0


@dataclass(frozen=True)
class RelationshipRuleHit:
    rule_id: str
    label: str  # always "Attention Pattern" per PROJECT_SPEC.md section 13
    description: str
    evidence: dict[str, float] = field(default_factory=dict)


def _g(year_map: YearMap, code: str, latest: int, prior: int) -> float | None:
    return growth_rate(year_map, code, latest, prior)


def _v(year_map: YearMap, code: str, year: int) -> float | None:
    return year_map.get(code, {}).get(year)


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


def _rule_payables_down_inventory_up(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    pay_g, inv_g = _g(year_map, "PAYABLES", latest, prior), _g(year_map, "INVENTORY", latest, prior)
    if pay_g is None or inv_g is None:
        return None
    if pay_g < -NOTABLE_GROWTH_PCT and inv_g > NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "PAYABLES_DOWN_INVENTORY_UP",
            "Attention Pattern",
            "매입채무는 감소했는데 재고자산은 증가했습니다. 공급처에 더 빨리 현금을 지급하며 재고를 늘리고 있는 것인지, "
            "거래조건이나 자금운용 변화가 있었는지 확인이 필요할 수 있습니다.",
            {"매입채무증가율": pay_g, "재고증가율": inv_g},
        )
    return None


def _rule_cash_down_borrowings_up(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    cash_g = _g(year_map, "CASH", latest, prior)
    if cash_g is None or cash_g >= -NOTABLE_GROWTH_PCT:
        return None
    lt_g, st_g = _g(year_map, "LT_BORROWINGS", latest, prior), _g(year_map, "ST_BORROWINGS", latest, prior)
    borrow_candidates = [g for g in (lt_g, st_g) if g is not None]
    if not borrow_candidates:
        return None
    borrow_g = max(borrow_candidates)
    if borrow_g > NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "CASH_DOWN_BORROWINGS_UP",
            "Attention Pattern",
            "현금및현금성자산은 줄었는데 차입금은 늘었습니다. 현금이 부족한 상황에서 외부 차입에 의존하고 있는 것인지 "
            "유동성 상황 확인이 필요할 수 있습니다.",
            {"현금증가율": cash_g, "차입금증가율": borrow_g},
        )
    return None


def _rule_sales_up_margin_down(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    sales_g = _g(year_map, "SALES", latest, prior)
    sales_latest, cogs_latest = _v(year_map, "SALES", latest), _v(year_map, "COGS", latest)
    sales_prior, cogs_prior = _v(year_map, "SALES", prior), _v(year_map, "COGS", prior)
    if None in (sales_g, sales_latest, cogs_latest, sales_prior, cogs_prior) or sales_latest == 0 or sales_prior == 0:
        return None
    if sales_g <= NOTABLE_GROWTH_PCT:
        return None
    margin_latest = (sales_latest - cogs_latest) / sales_latest * 100
    margin_prior = (sales_prior - cogs_prior) / sales_prior * 100
    margin_drop = margin_prior - margin_latest
    if margin_drop >= MARGIN_DROP_THRESHOLD_PP:
        return RelationshipRuleHit(
            "SALES_UP_MARGIN_DOWN",
            "Attention Pattern",
            "매출은 증가했는데 매출총이익률은 하락했습니다. 가격 경쟁이나 원가 상승 등 수익성 변화 원인 확인이 필요할 수 있습니다.",
            {"매출증가율": sales_g, "매출총이익률(전기)": round(margin_prior, 1), "매출총이익률(당기)": round(margin_latest, 1)},
        )
    return None


def _rule_intangible_up_ocf_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    intangible_g = _g(year_map, "INTANGIBLE_ASSETS", latest, prior)
    ocf_g = _g(year_map, "OPERATING_CF", latest, prior)
    if intangible_g is None or ocf_g is None:
        return None
    if intangible_g > MIN_DRIVING_GROWTH_PCT and abs(ocf_g) < FLAT_ABS_THRESHOLD_PCT:
        return RelationshipRuleHit(
            "INTANGIBLE_UP_OCF_FLAT",
            "Attention Pattern",
            "무형자산이 크게 증가했는데 영업활동현금흐름은 정체되어 있습니다. 비용을 자산으로 처리(자본화)했을 가능성이 있는지 "
            "확인이 필요할 수 있습니다.",
            {"무형자산증가율": intangible_g, "영업CF증가율": ocf_g},
        )
    return None


def _rule_retained_earnings_up_no_dividend_signal(
    year_map: YearMap, latest: int, prior: int
) -> RelationshipRuleHit | None:
    re_latest, re_prior = _v(year_map, "RETAINED_EARNINGS", latest), _v(year_map, "RETAINED_EARNINGS", prior)
    ni_latest = _v(year_map, "NET_INCOME", latest)
    if None in (re_latest, re_prior, ni_latest) or ni_latest <= 0:
        return None
    re_delta = re_latest - re_prior
    if re_delta <= 0:
        return None
    ratio = re_delta / ni_latest
    if ratio >= NO_DIVIDEND_RATIO_THRESHOLD:
        return RelationshipRuleHit(
            "RETAINED_EARNINGS_UP_NO_DIVIDEND_SIGNAL",
            "Attention Pattern",
            "이익잉여금 증가분이 당기순이익과 거의 같습니다. 배당 등 자본유출이 크지 않았던 것으로 보이며, "
            "배당정책이나 이익 유보 사유 확인이 필요할 수 있습니다.",
            {"이익잉여금증가/순이익비율(%)": round(ratio * 100, 1)},
        )
    return None


def _rule_capital_surplus_up_borrowings_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    cs_g = _g(year_map, "CAPITAL_SURPLUS", latest, prior)
    lt_g = _g(year_map, "LT_BORROWINGS", latest, prior)
    if cs_g is None or lt_g is None:
        return None
    if cs_g > MIN_DRIVING_GROWTH_PCT and abs(lt_g) < FLAT_ABS_THRESHOLD_PCT:
        return RelationshipRuleHit(
            "CAPITAL_SURPLUS_UP_BORROWINGS_FLAT",
            "Attention Pattern",
            "자본잉여금이 크게 증가했는데 차입금은 큰 변화가 없습니다. 유상증자 등으로 조달한 자금이 어디에 쓰였는지 "
            "확인이 필요할 수 있습니다.",
            {"자본잉여금증가율": cs_g, "차입금증가율": lt_g},
        )
    return None


def _rule_income_tax_swing_pretax_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    tax_g = _g(year_map, "INCOME_TAX_EXPENSE", latest, prior)
    pretax_g = _g(year_map, "PRETAX_INCOME", latest, prior)
    if tax_g is None or pretax_g is None:
        return None
    if abs(tax_g) > MIN_DRIVING_GROWTH_PCT and abs(pretax_g) < FLAT_ABS_THRESHOLD_PCT:
        return RelationshipRuleHit(
            "INCOME_TAX_SWING_PRETAX_FLAT",
            "Attention Pattern",
            "법인세비용차감전순이익은 안정적인데 법인세비용은 크게 변했습니다. 실효세율 변동, 일회성 세무조정이나 "
            "이연법인세 관련 이슈가 있었는지 확인이 필요할 수 있습니다.",
            {"법인세비용증가율": tax_g, "세전이익증가율": pretax_g},
        )
    return None


def _rule_receivable_up_allowance_lagging(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    recv_g = _g(year_map, "RECEIVABLE", latest, prior)
    allow_g = _g(year_map, "ALLOWANCE_DOUBTFUL", latest, prior)
    if recv_g is None or allow_g is None:
        return None
    if recv_g > NOTABLE_GROWTH_PCT and allow_g < recv_g - FASTER_MARGIN_PP:
        return RelationshipRuleHit(
            "RECEIVABLE_UP_ALLOWANCE_LAGGING",
            "Attention Pattern",
            "매출채권은 증가했는데 대손충당금은 그에 못 미치게 늘었거나 오히려 감소했습니다. 대손율 산정 근거 변경 여부 "
            "확인이 필요할 수 있습니다.",
            {"매출채권증가율": recv_g, "대손충당금증가율": allow_g},
        )
    return None


def _rule_payables_up_cogs_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    pay_g = _g(year_map, "PAYABLES", latest, prior)
    cogs_g = _g(year_map, "COGS", latest, prior)
    if pay_g is None or cogs_g is None:
        return None
    if pay_g > NOTABLE_GROWTH_PCT and cogs_g < NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "PAYABLES_UP_COGS_FLAT",
            "Attention Pattern",
            "매입채무는 증가했는데 매출원가는 정체되어 있습니다. 매입분이 재고로 쌓이고 있거나 지급조건이 바뀐 것인지 "
            "확인이 필요할 수 있습니다.",
            {"매입채무증가율": pay_g, "매출원가증가율": cogs_g},
        )
    return None


def _rule_tangible_assets_up_depreciation_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    # Coarse-data counterpart to _rule_capex_up_depreciation_flat, for
    # companies where the granular STRUCTURE/MACHINERY breakdown isn't
    # available and 유형자산 is the only capex signal on hand — same reason
    # narrative_patterns.py's PRODUCTION_EXPANSION/CAPEX_FINANCING clusters
    # fall back to TANGIBLE_ASSETS.
    ta_g = _g(year_map, "TANGIBLE_ASSETS", latest, prior)
    dep_g = _g(year_map, "DEPRECIATION", latest, prior)
    if ta_g is None or dep_g is None:
        return None
    if ta_g > MIN_DRIVING_GROWTH_PCT and dep_g < ta_g * SMALL_CHANGE_FRACTION:
        return RelationshipRuleHit(
            "TANGIBLE_ASSETS_UP_DEPRECIATION_FLAT",
            "Attention Pattern",
            "유형자산이 크게 증가했는데 감가상각비 변화는 상대적으로 작습니다. 신규 자산의 가동 개시 시점이나 감가상각 "
            "정책을 확인할 필요가 있을 수 있습니다.",
            {"유형자산증가율": ta_g, "감가상각비증가율": dep_g},
        )
    return None


def _rule_oci_swing_net_income_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    oci_latest, oci_prior = _v(year_map, "OTHER_COMPREHENSIVE_INCOME", latest), _v(
        year_map, "OTHER_COMPREHENSIVE_INCOME", prior
    )
    ni_latest = _v(year_map, "NET_INCOME", latest)
    ni_g = _g(year_map, "NET_INCOME", latest, prior)
    if None in (oci_latest, oci_prior, ni_latest, ni_g) or ni_latest == 0:
        return None
    swing_ratio = abs(oci_latest - oci_prior) / abs(ni_latest) * 100
    if swing_ratio >= OCI_MATERIALITY_RATIO_PCT and abs(ni_g) < FLAT_ABS_THRESHOLD_PCT:
        return RelationshipRuleHit(
            "OCI_SWING_NET_INCOME_FLAT",
            "Attention Pattern",
            "당기순이익은 안정적인데 기타포괄손익이 크게 변동했습니다. 공정가치평가나 해외사업환산 등 손익계산서에 "
            "잡히지 않는 항목의 변동 원인 확인이 필요할 수 있습니다.",
            {"기타포괄손익변동/순이익비율(%)": round(swing_ratio, 1), "순이익증가율": ni_g},
        )
    return None


def _rule_inventory_up_cogs_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    inv_g = _g(year_map, "INVENTORY", latest, prior)
    cogs_g = _g(year_map, "COGS", latest, prior)
    if inv_g is None or cogs_g is None:
        return None
    if inv_g > NOTABLE_GROWTH_PCT and cogs_g < NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "INVENTORY_UP_COGS_FLAT",
            "Attention Pattern",
            "재고자산은 증가했는데 매출원가는 정체되어 있습니다. 재고가 판매로 이어지지 않고 쌓이는 것인지(재고회전율 "
            "하락 가능성), 진부화·과잉재고 리스크 확인이 필요할 수 있습니다.",
            {"재고증가율": inv_g, "매출원가증가율": cogs_g},
        )
    return None


def _rule_st_borrowings_up_lt_borrowings_down(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    st_g = _g(year_map, "ST_BORROWINGS", latest, prior)
    lt_g = _g(year_map, "LT_BORROWINGS", latest, prior)
    if st_g is None or lt_g is None:
        return None
    if st_g > NOTABLE_GROWTH_PCT and lt_g < -NOTABLE_GROWTH_PCT:
        return RelationshipRuleHit(
            "ST_BORROWINGS_UP_LT_BORROWINGS_DOWN",
            "Attention Pattern",
            "단기차입금은 늘고 장기차입금은 줄었습니다. 장기차입을 단기로 갈아탄 것인지, 만기 임박이나 차환 리스크가 "
            "있는지 확인이 필요할 수 있습니다.",
            {"단기차입금증가율": st_g, "장기차입금증가율": lt_g},
        )
    return None


def _rule_tax_payable_up_tax_expense_flat(year_map: YearMap, latest: int, prior: int) -> RelationshipRuleHit | None:
    tp_g = _g(year_map, "TAX_PAYABLE", latest, prior)
    tax_g = _g(year_map, "INCOME_TAX_EXPENSE", latest, prior)
    if tp_g is None or tax_g is None:
        return None
    if tp_g > MIN_DRIVING_GROWTH_PCT and abs(tax_g) < FLAT_ABS_THRESHOLD_PCT:
        return RelationshipRuleHit(
            "TAX_PAYABLE_UP_TAX_EXPENSE_FLAT",
            "Attention Pattern",
            "미지급법인세가 크게 증가했는데 법인세비용은 안정적입니다. 세금 납부가 지연되고 있는 것인지, 현금흐름이나 "
            "세무조사 대응 상황 확인이 필요할 수 있습니다.",
            {"미지급법인세증가율": tp_g, "법인세비용증가율": tax_g},
        )
    return None


def _rule_equity_method_investment_up_gain_loss_swing(
    year_map: YearMap, latest: int, prior: int
) -> RelationshipRuleHit | None:
    emi_g = _g(year_map, "EQUITY_METHOD_INVESTMENT", latest, prior)
    eml_g = _g(year_map, "EQUITY_METHOD_GAIN_LOSS", latest, prior)
    if emi_g is None or eml_g is None:
        return None
    if emi_g > NOTABLE_GROWTH_PCT and abs(eml_g) > MIN_DRIVING_GROWTH_PCT:
        return RelationshipRuleHit(
            "EQUITY_METHOD_INVESTMENT_UP_GAIN_LOSS_SWING",
            "Attention Pattern",
            "관계기업및공동기업투자자산이 증가한 가운데 지분법손익이 크게 변동했습니다. 지분법 적용회사의 실적이나 "
            "투자 회수 가능성 확인이 필요할 수 있습니다.",
            {"관계기업투자자산증가율": emi_g, "지분법손익증가율": eml_g},
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
    _rule_payables_down_inventory_up,
    _rule_cash_down_borrowings_up,
    _rule_sales_up_margin_down,
    _rule_intangible_up_ocf_flat,
    _rule_retained_earnings_up_no_dividend_signal,
    _rule_capital_surplus_up_borrowings_flat,
    _rule_income_tax_swing_pretax_flat,
    _rule_receivable_up_allowance_lagging,
    _rule_payables_up_cogs_flat,
    _rule_tangible_assets_up_depreciation_flat,
    _rule_oci_swing_net_income_flat,
    _rule_inventory_up_cogs_flat,
    _rule_st_borrowings_up_lt_borrowings_down,
    _rule_tax_payable_up_tax_expense_flat,
    _rule_equity_method_investment_up_gain_loss_swing,
)


def detect_relationship_rules(year_map: YearMap, latest: int, prior: int) -> list[RelationshipRuleHit]:
    hits = (rule(year_map, latest, prior) for rule in _ALL_RULES)
    return [hit for hit in hits if hit is not None]
