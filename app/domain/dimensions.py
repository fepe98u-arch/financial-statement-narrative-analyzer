"""Business-dimension classification for accounts.

PROJECT_SPEC.md section 11: accounts are grouped into business-meaning
dimensions (not just accounting categories) so the pattern engines can
reason about clusters like "CAPEX / FINANCING" instead of comparing every
possible pair of accounts (section 15).
"""
from __future__ import annotations

from enum import Enum


class BusinessDimension(str, Enum):
    SALES = "SALES"
    RECEIVABLE = "RECEIVABLE"
    INVENTORY = "INVENTORY"
    OPERATING_COST = "OPERATING_COST"
    CAPEX = "CAPEX"
    FINANCING = "FINANCING"
    CASH_GENERATION = "CASH_GENERATION"
    PROFIT = "PROFIT"
    R_AND_D = "R_AND_D"
    CREDIT_RISK = "CREDIT_RISK"


# account_code -> BusinessDimension. Extend this as new accounts are added
# to the synthetic (and later, real) data loaders.
ACCOUNT_DIMENSION: dict[str, BusinessDimension] = {
    "SALES": BusinessDimension.SALES,
    "RECEIVABLE": BusinessDimension.RECEIVABLE,
    "INVENTORY": BusinessDimension.INVENTORY,
    "COGS": BusinessDimension.OPERATING_COST,
    "STRUCTURE": BusinessDimension.CAPEX,
    "MACHINERY": BusinessDimension.CAPEX,
    "CONSTRUCTION_IN_PROGRESS": BusinessDimension.CAPEX,
    "DEPRECIATION": BusinessDimension.CAPEX,
    "LT_BORROWINGS": BusinessDimension.FINANCING,
    "INTEREST_EXPENSE": BusinessDimension.FINANCING,
    "OPERATING_CF": BusinessDimension.CASH_GENERATION,
    "OPERATING_PROFIT": BusinessDimension.PROFIT,
    "NET_INCOME": BusinessDimension.PROFIT,
    "ALLOWANCE_DOUBTFUL": BusinessDimension.CREDIT_RISK,
}

# Human-readable account names, kept in one place so the UI, the normalizer,
# and the engines never disagree on labels.
CANONICAL_ACCOUNT_NAMES: dict[str, str] = {
    "SALES": "매출",
    "RECEIVABLE": "매출채권",
    "INVENTORY": "재고자산",
    "COGS": "매출원가",
    "STRUCTURE": "구축물",
    "MACHINERY": "기계장치",
    "CONSTRUCTION_IN_PROGRESS": "건설중인자산",
    "DEPRECIATION": "감가상각비",
    "LT_BORROWINGS": "장기차입금",
    "INTEREST_EXPENSE": "이자비용",
    "OPERATING_CF": "영업활동현금흐름",
    "OPERATING_PROFIT": "영업이익",
    "NET_INCOME": "순이익",
    "ALLOWANCE_DOUBTFUL": "대손충당금",
    "TOTAL_ASSETS": "총자산",
}

# Which DART sj_div (statement section) each canonical account's value
# should actually come from. Real filings often report the *same* raw
# label in more than one statement (e.g. "당기순이익" appears in the income
# statement, again in the cash-flow reconciliation, and again in the
# statement of changes in equity) — without this, an exact-name match in
# the wrong statement would auto-accept just as readily as the right one.
# Used only to decide what to *pre-select* in the import UI; it never
# blocks a user from manually choosing something else.
PREFERRED_STATEMENT_SECTIONS: dict[str, tuple[str, ...]] = {
    "SALES": ("IS", "CIS"),
    "COGS": ("IS", "CIS"),
    "OPERATING_PROFIT": ("IS", "CIS"),
    "NET_INCOME": ("IS", "CIS"),
    "DEPRECIATION": ("IS", "CIS"),
    "INTEREST_EXPENSE": ("IS", "CIS"),
    "RECEIVABLE": ("BS",),
    "INVENTORY": ("BS",),
    "STRUCTURE": ("BS",),
    "MACHINERY": ("BS",),
    "CONSTRUCTION_IN_PROGRESS": ("BS",),
    "LT_BORROWINGS": ("BS",),
    "TOTAL_ASSETS": ("BS",),
    "ALLOWANCE_DOUBTFUL": ("BS",),
    "OPERATING_CF": ("CF",),
}
