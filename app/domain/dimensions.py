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
    LIQUIDITY = "LIQUIDITY"
    WORKING_CAPITAL = "WORKING_CAPITAL"
    EQUITY = "EQUITY"
    TAX = "TAX"
    OTHER_COMPREHENSIVE = "OTHER_COMPREHENSIVE"
    EQUITY_METHOD = "EQUITY_METHOD"


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
    "TANGIBLE_ASSETS": BusinessDimension.CAPEX,
    "INTANGIBLE_ASSETS": BusinessDimension.CAPEX,
    "DEPRECIATION": BusinessDimension.CAPEX,
    "LT_BORROWINGS": BusinessDimension.FINANCING,
    "ST_BORROWINGS": BusinessDimension.FINANCING,
    "INTEREST_EXPENSE": BusinessDimension.FINANCING,
    "OPERATING_CF": BusinessDimension.CASH_GENERATION,
    "CASH": BusinessDimension.LIQUIDITY,
    "OPERATING_PROFIT": BusinessDimension.PROFIT,
    "NET_INCOME": BusinessDimension.PROFIT,
    "PRETAX_INCOME": BusinessDimension.PROFIT,
    "ALLOWANCE_DOUBTFUL": BusinessDimension.CREDIT_RISK,
    "PAYABLES": BusinessDimension.WORKING_CAPITAL,
    "RETAINED_EARNINGS": BusinessDimension.EQUITY,
    "CAPITAL_SURPLUS": BusinessDimension.EQUITY,
    "INCOME_TAX_EXPENSE": BusinessDimension.TAX,
    "TAX_PAYABLE": BusinessDimension.TAX,
    "OTHER_COMPREHENSIVE_INCOME": BusinessDimension.OTHER_COMPREHENSIVE,
    "EQUITY_METHOD_INVESTMENT": BusinessDimension.EQUITY_METHOD,
    "EQUITY_METHOD_GAIN_LOSS": BusinessDimension.EQUITY_METHOD,
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
    # DART's summary financial-statement API (fnlttSinglAcntAll, what the
    # DART import currently uses) reports 유형자산 as a single combined
    # line — the STRUCTURE/MACHINERY/CONSTRUCTION_IN_PROGRESS breakdown only
    # exists in the filing's notes, a different data source. TANGIBLE_ASSETS
    # is the coarser combined figure narrative_patterns.py falls back to for
    # companies where that breakdown isn't available.
    "TANGIBLE_ASSETS": "유형자산",
    "INTANGIBLE_ASSETS": "무형자산",
    "DEPRECIATION": "감가상각비",
    "LT_BORROWINGS": "장기차입금",
    "ST_BORROWINGS": "단기차입금",
    "INTEREST_EXPENSE": "이자비용",
    "OPERATING_CF": "영업활동현금흐름",
    "CASH": "현금및현금성자산",
    "OPERATING_PROFIT": "영업이익",
    "NET_INCOME": "순이익",
    "PRETAX_INCOME": "법인세비용차감전순이익",
    "ALLOWANCE_DOUBTFUL": "대손충당금",
    "TOTAL_ASSETS": "총자산",
    "PAYABLES": "매입채무",
    "RETAINED_EARNINGS": "이익잉여금",
    "CAPITAL_SURPLUS": "자본잉여금",
    "INCOME_TAX_EXPENSE": "법인세비용",
    "TAX_PAYABLE": "미지급법인세",
    "OTHER_COMPREHENSIVE_INCOME": "기타포괄손익",
    "EQUITY_METHOD_INVESTMENT": "관계기업및공동기업투자자산",
    "EQUITY_METHOD_GAIN_LOSS": "지분법손익",
}

# Which single DART sj_div (statement section) each canonical account's
# value should actually come from. Real filings often report the *same*
# raw label in more than one statement — not just "당기순이익" in the
# income statement, the cash-flow reconciliation, and the statement of
# changes in equity, but also (very commonly) the income statement's own
# bottom line repeated verbatim as the first line of the comprehensive
# income statement (IS and CIS reporting the identical 당기순이익 figure
# is standard practice, not a rare edge case). Allowing *both* as
# "preferred" meant both auto-accepted and collided on save. Exactly one
# section is preferred per account — everything else still shows up in the
# mapping table for a human to pick manually, this only controls what gets
# pre-selected.
PREFERRED_STATEMENT_SECTIONS: dict[str, str] = {
    "SALES": "IS",
    "COGS": "IS",
    "OPERATING_PROFIT": "IS",
    "NET_INCOME": "IS",
    "PRETAX_INCOME": "IS",
    "INCOME_TAX_EXPENSE": "IS",
    "EQUITY_METHOD_GAIN_LOSS": "IS",
    "OTHER_COMPREHENSIVE_INCOME": "CIS",
    # Real filings from Samsung and Yuhan both reported these as a separate
    # exact-match line inside the cash-flow statement (as a non-cash
    # addback / supplemental disclosure) — the income statement rarely
    # breaks them out as their own top-level line (they're usually folded
    # into COGS/SG&A there), so CF is the more reliable single source.
    "DEPRECIATION": "CF",
    "INTEREST_EXPENSE": "CF",
    "RECEIVABLE": "BS",
    "INVENTORY": "BS",
    "STRUCTURE": "BS",
    "MACHINERY": "BS",
    "CONSTRUCTION_IN_PROGRESS": "BS",
    "TANGIBLE_ASSETS": "BS",
    "INTANGIBLE_ASSETS": "BS",
    "LT_BORROWINGS": "BS",
    "ST_BORROWINGS": "BS",
    "CASH": "BS",
    "PAYABLES": "BS",
    "RETAINED_EARNINGS": "BS",
    "CAPITAL_SURPLUS": "BS",
    "TAX_PAYABLE": "BS",
    "EQUITY_METHOD_INVESTMENT": "BS",
    "TOTAL_ASSETS": "BS",
    "ALLOWANCE_DOUBTFUL": "BS",
    "OPERATING_CF": "CF",
}
