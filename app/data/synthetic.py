"""Synthetic 5-year financial data for fictional companies.

No real company, client, or audit data is used anywhere in this project.
See PROJECT_SPEC.md section 5 and section 51.

Two companies, two different narrative patterns:

- ABC Manufacturing: inventory down while structures/machinery/construction-
  in-progress/borrowings intensify by 2026 — the CAPEX/financing pattern in
  PROJECT_SPEC.md section 47 (numbers chosen to hit -38% / +82% / +51% /
  +70% YoY for 2026, matching that example almost exactly).
- Sample Electronics: sales declining while receivables and the doubtful-
  debt allowance rise, and operating cash flow falls even as net income
  ticks up — the "separate pattern" described in section 51 (매출 감소,
  매출채권 증가, 영업CF 감소, 대손충당금 증가).
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DIR = PROJECT_ROOT / ".tmp" / "synthetic"
SYNTHETIC_CSV = SYNTHETIC_DIR / "financial_facts.csv"

# unit: KRW millions
YEARS = [2022, 2023, 2024, 2025, 2026]

# company_name -> {account_code: (account_name, values for YEARS)}
COMPANIES: dict[str, dict[str, tuple[str, list[int]]]] = {
    "ABC Manufacturing": {
        "SALES": ("매출", [118_000, 123_500, 128_800, 133_600, 137_200]),
        "RECEIVABLE": ("매출채권", [14_200, 14_800, 15_500, 16_700, 18_100]),
        "INVENTORY": ("재고자산", [19_800, 18_900, 17_600, 14_200, 8_800]),
        "COGS": ("매출원가", [82_600, 86_450, 90_160, 93_520, 96_040]),
        "STRUCTURE": ("구축물", [10_800, 12_100, 14_600, 19_200, 34_900]),
        "MACHINERY": ("기계장치", [23_600, 25_900, 29_400, 37_200, 56_200]),
        "CONSTRUCTION_IN_PROGRESS": ("건설중인자산", [3_200, 3_600, 4_300, 5_800, 12_400]),
        "DEPRECIATION": ("감가상각비", [4_200, 4_500, 4_900, 5_300, 5_600]),
        "LT_BORROWINGS": ("장기차입금", [29_500, 32_800, 38_100, 50_500, 85_850]),
        "INTEREST_EXPENSE": ("이자비용", [1_300, 1_450, 1_620, 1_800, 1_900]),
        "OPERATING_CF": ("영업활동현금흐름", [13_200, 14_100, 14_800, 13_900, 10_600]),
        "OPERATING_PROFIT": ("영업이익", [11_800, 12_100, 12_500, 12_700, 12_200]),
        "NET_INCOME": ("순이익", [8_200, 8_500, 8_700, 8_300, 7_100]),
        "TOTAL_ASSETS": ("총자산", [210_000, 225_000, 242_000, 268_000, 320_000]),
    },
    "Sample Electronics": {
        "SALES": ("매출", [95_000, 93_500, 91_000, 86_000, 78_000]),
        "RECEIVABLE": ("매출채권", [11_000, 11_800, 12_900, 14_600, 17_800]),
        "INVENTORY": ("재고자산", [9_000, 9_200, 9_400, 9_600, 9_800]),
        "COGS": ("매출원가", [66_500, 65_450, 63_700, 60_200, 54_600]),
        "OPERATING_CF": ("영업활동현금흐름", [7_200, 6_900, 6_300, 5_400, 3_900]),
        "OPERATING_PROFIT": ("영업이익", [8_100, 7_600, 7_000, 6_800, 6_900]),
        "NET_INCOME": ("순이익", [6_200, 6_000, 5_700, 6_000, 6_500]),
        "ALLOWANCE_DOUBTFUL": ("대손충당금", [800, 950, 1_150, 1_500, 2_300]),
        "TOTAL_ASSETS": ("총자산", [120_000, 121_500, 122_800, 124_000, 126_500]),
    },
}


def build_synthetic_dataframe() -> pl.DataFrame:
    rows = [
        {
            "company": company,
            "year": year,
            "account_code": code,
            "account_name": name,
            "amount": amount,
            "unit": "KRW_MILLION",
        }
        for company, accounts in COMPANIES.items()
        for code, (name, values) in accounts.items()
        for year, amount in zip(YEARS, values)
    ]
    return pl.DataFrame(rows)


def write_synthetic_csv(path: Path = SYNTHETIC_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    build_synthetic_dataframe().write_csv(path)
    return path


def ensure_synthetic_csv(path: Path = SYNTHETIC_CSV) -> Path:
    """Regenerate the synthetic CSV if it's missing. .tmp/ is throwaway by
    design (see CLAUDE.md), so this is safe to call on every startup."""
    if not path.exists():
        write_synthetic_csv(path)
    return path
