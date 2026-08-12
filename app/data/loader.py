"""Local-only Polars loader for financial fact data.

Reads exclusively from the local filesystem — the synthetic fixture CSV,
plus (if present) user-imported Excel/CSV data saved by
app/data/statement_import.py. Nothing in this module performs network I/O
— see PROJECT_SPEC.md section 23 for why that boundary matters.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.synthetic import ensure_synthetic_csv
from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORTED_DIR = PROJECT_ROOT / "data" / "imported"
IMPORTED_CSV = IMPORTED_DIR / "imported_financials.csv"

# Canonical accounts, in one fixed display order shared by every company —
# real imported companies rarely have every account, so tables/UI just
# filter this down to whatever's actually present (see account_order_for).
MASTER_ACCOUNT_ORDER = list(CANONICAL_ACCOUNT_NAMES.keys())


def _read_facts_csv(path: Path) -> pl.DataFrame:
    # pl.read_csv infers "amount" as Int64 when every value in a file
    # happens to be a whole number (true of the synthetic fixture) and
    # Float64 otherwise (true of most real imports) — force Float64 always
    # so synthetic + imported frames always concat cleanly.
    return pl.read_csv(path).with_columns(pl.col("amount").cast(pl.Float64))


def load_financial_facts(csv_path: Path | None = None) -> pl.DataFrame:
    if csv_path is not None:
        return _read_facts_csv(csv_path)

    synthetic_facts = _read_facts_csv(ensure_synthetic_csv())
    if not IMPORTED_CSV.exists():
        return synthetic_facts

    imported_facts = _read_facts_csv(IMPORTED_CSV)
    # Imported data wins on overlap (e.g. someone imports real data under a
    # name that collides with a synthetic fixture) — avoids duplicate
    # (company, year, account_code) rows, which would break the pivot below.
    key_cols = ["company", "year", "account_code"]
    synthetic_facts = synthetic_facts.join(imported_facts.select(key_cols), on=key_cols, how="anti")
    return pl.concat([synthetic_facts, imported_facts])


def list_companies(facts: pl.DataFrame) -> list[str]:
    return sorted(facts["company"].unique().to_list())


def filter_company(facts: pl.DataFrame, company: str) -> pl.DataFrame:
    return facts.filter(pl.col("company") == company)


def years_for_company(facts: pl.DataFrame, company: str) -> list[int]:
    company_facts = filter_company(facts, company)
    return sorted(int(y) for y in company_facts["year"].unique().to_list())


def account_order_for(company_facts: pl.DataFrame) -> list[str]:
    present = set(company_facts["account_code"].unique().to_list())
    return [code for code in MASTER_ACCOUNT_ORDER if code in present]


def build_dashboard_table(
    facts: pl.DataFrame, company: str
) -> tuple[pl.DataFrame, list[int]]:
    """Pivot one company's long-format facts into one row per account, one
    column per year, plus a YoY% column comparing the two most recent
    years."""
    company_facts = filter_company(facts, company)
    years = sorted(int(y) for y in company_facts["year"].unique().to_list())

    wide = company_facts.pivot(
        values="amount", index=["account_code", "account_name"], on="year"
    )
    if len(years) >= 2:
        latest, prior = years[-1], years[-2]
        wide = wide.with_columns(
            ((pl.col(str(latest)) - pl.col(str(prior))) / pl.col(str(prior)) * 100)
            .round(1)
            .alias("yoy_pct")
        )
    else:
        wide = wide.with_columns(pl.lit(None, dtype=pl.Float64).alias("yoy_pct"))

    order_list = account_order_for(company_facts)
    order = pl.DataFrame({"account_code": order_list, "_order": list(range(len(order_list)))})
    wide = wide.join(order, on="account_code", how="inner").sort("_order").drop("_order")
    return wide, years


def to_year_map(facts: pl.DataFrame, company: str) -> dict[str, dict[int, float]]:
    """account_code -> {year: amount}, the shape the metrics/rules/pattern
    engines consume. Only accounts actually present for this company show
    up here — nothing is padded or guessed (PROJECT_SPEC.md section 12)."""
    company_facts = filter_company(facts, company)
    year_map: dict[str, dict[int, float]] = {}
    for row in company_facts.iter_rows(named=True):
        year_map.setdefault(row["account_code"], {})[int(row["year"])] = float(row["amount"])
    return year_map


def account_name_map(facts: pl.DataFrame, company: str) -> dict[str, str]:
    company_facts = filter_company(facts, company)
    return dict(
        zip(
            company_facts["account_code"].to_list(),
            company_facts["account_name"].to_list(),
        )
    )
