"""Local-only Polars loader for financial fact data.

Reads exclusively from the local filesystem (synthetic CSV for now, real
Excel/CSV uploads in a later phase). Nothing in this module performs network
I/O — see PROJECT_SPEC.md section 23 for why that boundary matters.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.synthetic import COMPANIES, ensure_synthetic_csv


def load_financial_facts(csv_path: Path | None = None) -> pl.DataFrame:
    path = csv_path or ensure_synthetic_csv()
    return pl.read_csv(path)


def list_companies(facts: pl.DataFrame) -> list[str]:
    return sorted(facts["company"].unique().to_list())


def filter_company(facts: pl.DataFrame, company: str) -> pl.DataFrame:
    return facts.filter(pl.col("company") == company)


def account_order(company: str) -> list[str]:
    """Preserve the order accounts are defined in for a given company, so
    tables/UI show them in a stable, meaningful sequence rather than
    alphabetically."""
    return list(COMPANIES.get(company, {}).keys())


def build_dashboard_table(
    facts: pl.DataFrame, company: str
) -> tuple[pl.DataFrame, list[int]]:
    """Pivot one company's long-format facts into one row per account, one
    column per year, plus a YoY% column comparing the two most recent
    years."""
    company_facts = filter_company(facts, company)
    years = sorted(int(y) for y in company_facts["year"].unique().to_list())
    latest, prior = years[-1], years[-2]

    wide = company_facts.pivot(
        values="amount", index=["account_code", "account_name"], on="year"
    )
    wide = wide.with_columns(
        ((pl.col(str(latest)) - pl.col(str(prior))) / pl.col(str(prior)) * 100)
        .round(1)
        .alias("yoy_pct")
    )

    order = pl.DataFrame(
        {
            "account_code": account_order(company),
            "_order": list(range(len(account_order(company)))),
        }
    )
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
