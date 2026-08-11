"""Basic financial metrics (PROJECT_SPEC.md section 12).

Every function here only returns a value when every account it needs is
actually present for that company/year — nothing is estimated or guessed
("계산 불가능한 값은 임의로 추정하지 않는다"). Missing inputs mean the
metric is simply omitted (`None`), not filled in with a placeholder.
"""
from __future__ import annotations

from dataclasses import dataclass

YearMap = dict[str, dict[int, float]]

CAPEX_ACCOUNTS = ("STRUCTURE", "MACHINERY", "CONSTRUCTION_IN_PROGRESS")


def _get(year_map: YearMap, code: str, year: int) -> float | None:
    return year_map.get(code, {}).get(year)


def growth_rate(year_map: YearMap, code: str, latest: int, prior: int) -> float | None:
    curr = _get(year_map, code, latest)
    prev = _get(year_map, code, prior)
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / prev * 100, 1)


def ratio_pct(year_map: YearMap, numerator: str, denominator: str, year: int) -> float | None:
    num = _get(year_map, numerator, year)
    den = _get(year_map, denominator, year)
    if num is None or den is None or den == 0:
        return None
    return round(num / den * 100, 1)


def dso(year_map: YearMap, year: int) -> float | None:
    """Days Sales Outstanding = 매출채권 / 매출 * 365."""
    receivable = _get(year_map, "RECEIVABLE", year)
    sales = _get(year_map, "SALES", year)
    if receivable is None or sales is None or sales == 0:
        return None
    return round(receivable / sales * 365, 1)


def inventory_turnover(year_map: YearMap, year: int) -> float | None:
    """매출원가 / 평균재고. Falls back to period-end inventory if the prior
    year isn't available to average."""
    cogs = _get(year_map, "COGS", year)
    inv_curr = _get(year_map, "INVENTORY", year)
    if cogs is None or inv_curr is None:
        return None
    inv_prior = _get(year_map, "INVENTORY", year - 1)
    avg_inventory = (inv_curr + inv_prior) / 2 if inv_prior is not None else inv_curr
    if avg_inventory == 0:
        return None
    return round(cogs / avg_inventory, 2)


def capex_total(year_map: YearMap, year: int) -> float | None:
    values = [_get(year_map, code, year) for code in CAPEX_ACCOUNTS]
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(sum(present), 1)


@dataclass(frozen=True)
class MetricResult:
    key: str
    label: str
    value: float
    unit: str  # "%", "일", "회", "백만원"


def compute_all_metrics(year_map: YearMap, latest: int, prior: int) -> list[MetricResult]:
    results: list[MetricResult] = []

    growth_specs = [
        ("SALES", "매출증가율"),
        ("OPERATING_PROFIT", "영업이익증가율"),
        ("RECEIVABLE", "매출채권증가율"),
        ("INVENTORY", "재고증가율"),
        ("LT_BORROWINGS", "차입금증가율"),
        ("OPERATING_CF", "영업CF증가율"),
    ]
    for code, label in growth_specs:
        value = growth_rate(year_map, code, latest, prior)
        if value is not None:
            results.append(MetricResult(f"{code}_GROWTH", label, value, "%"))

    fixed_asset_growth_inputs = [
        growth_rate(year_map, code, latest, prior) for code in ("STRUCTURE", "MACHINERY")
    ]
    fixed_asset_growth_inputs = [v for v in fixed_asset_growth_inputs if v is not None]
    if fixed_asset_growth_inputs:
        results.append(
            MetricResult(
                "FIXED_ASSET_GROWTH",
                "유형자산증가율(구축물·기계장치 평균)",
                round(sum(fixed_asset_growth_inputs) / len(fixed_asset_growth_inputs), 1),
                "%",
            )
        )

    ratio_specs = [
        ("RECEIVABLE", "SALES", "매출채권/매출"),
        ("INVENTORY", "SALES", "재고/매출"),
        ("LT_BORROWINGS", "TOTAL_ASSETS", "차입금/총자산"),
        ("OPERATING_CF", "NET_INCOME", "영업CF/순이익"),
    ]
    for num, den, label in ratio_specs:
        value = ratio_pct(year_map, num, den, latest)
        if value is not None:
            results.append(MetricResult(f"{num}_OVER_{den}", label, value, "%"))

    dso_value = dso(year_map, latest)
    if dso_value is not None:
        results.append(MetricResult("DSO", "매출채권회전일수(DSO)", dso_value, "일"))

    turnover_value = inventory_turnover(year_map, latest)
    if turnover_value is not None:
        results.append(MetricResult("INVENTORY_TURNOVER", "재고회전율", turnover_value, "회"))

    capex_latest = capex_total(year_map, latest)
    capex_prior = capex_total(year_map, prior)
    if capex_latest is not None and capex_prior is not None and capex_prior != 0:
        results.append(
            MetricResult(
                "CAPEX_GROWTH",
                "CAPEX증가율(구축물+기계장치+건설중인자산)",
                round((capex_latest - capex_prior) / capex_prior * 100, 1),
                "%",
            )
        )

    return results
