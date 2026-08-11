"""Historical Pattern Engine (PROJECT_SPEC.md section 17).

Compares the latest YoY move for an account against the same account's
moves in earlier transitions in the dataset (up to the 3-5 years the spec
calls for), and classifies it — never inventing a cause, just describing
how this year's move compares to the account's own recent history.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.analysis.metrics_engine import YearMap, growth_rate

NOTABLE_GROWTH_PCT = 10.0
INTENSIFY_FACTOR = 1.5


class HistoricalClassification(str, Enum):
    NEW_PATTERN = "NEW_PATTERN"
    RECURRING_PATTERN = "RECURRING_PATTERN"
    INTENSIFIED_PATTERN = "INTENSIFIED_PATTERN"
    NORMAL_RANGE = "NORMAL_RANGE"
    REVERSAL_PATTERN = "REVERSAL_PATTERN"


@dataclass(frozen=True)
class AccountHistoricalPattern:
    account_code: str
    account_name: str
    current_growth: float
    historical_growths: dict[int, float]  # transition-year -> growth %
    classification: HistoricalClassification


def _transition_growths(year_map: YearMap, code: str, years: list[int]) -> dict[int, float]:
    """growth_rate for every consecutive year pair in `years`, keyed by the
    later year of the pair."""
    growths: dict[int, float] = {}
    for later, earlier in zip(years[1:], years[:-1]):
        g = growth_rate(year_map, code, later, earlier)
        if g is not None:
            growths[later] = g
    return growths


def classify_account_history(
    year_map: YearMap, code: str, account_name: str, years: list[int]
) -> AccountHistoricalPattern | None:
    """`years` must be sorted ascending and include at least the latest and
    prior year. Everything before the latest transition is "history"."""
    latest, prior = years[-1], years[-2]
    current_growth = growth_rate(year_map, code, latest, prior)
    if current_growth is None:
        return None

    historical_growths = _transition_growths(year_map, code, years[:-1])  # excludes latest transition

    current_notable = abs(current_growth) >= NOTABLE_GROWTH_PCT
    notable_historical = {y: g for y, g in historical_growths.items() if abs(g) >= NOTABLE_GROWTH_PCT}

    if not current_notable:
        classification = HistoricalClassification.NORMAL_RANGE
    elif not notable_historical:
        classification = HistoricalClassification.NEW_PATTERN
    else:
        same_direction = {y: g for y, g in notable_historical.items() if (g > 0) == (current_growth > 0)}
        if same_direction:
            max_hist_magnitude = max(abs(g) for g in same_direction.values())
            if abs(current_growth) >= max_hist_magnitude * INTENSIFY_FACTOR:
                classification = HistoricalClassification.INTENSIFIED_PATTERN
            else:
                classification = HistoricalClassification.RECURRING_PATTERN
        else:
            classification = HistoricalClassification.REVERSAL_PATTERN

    return AccountHistoricalPattern(code, account_name, current_growth, historical_growths, classification)


def classify_all_accounts(
    year_map: YearMap, account_names: dict[str, str], years: list[int]
) -> list[AccountHistoricalPattern]:
    results = []
    for code in year_map:
        name = account_names.get(code, code)
        result = classify_account_history(year_map, code, name, years)
        if result is not None:
            results.append(result)
    return results
