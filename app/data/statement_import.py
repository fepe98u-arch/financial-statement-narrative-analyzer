"""Financial Data Loader — Excel/CSV import (PROJECT_SPEC.md section 8).

Reads a structured spreadsheet from the local filesystem only — nothing
here uploads anywhere. No PDF/OCR support yet (section 8 explicitly
deprioritizes that). Expected shape: first column is the raw account name,
every other column is a 4-digit year header:

    계정과목   | 2023   | 2024   | 2025
    매출       | 100000 | 110000 | 120000
    매출채권   | 12000  | 13000  | 14000

Raw account names go through the Account Normalizer (section 10) before
anything is saved — ambiguous rows are surfaced for the user to resolve or
skip, never guessed automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from app.analysis.account_normalizer import AccountMapping, normalize_account_name
from app.data.loader import IMPORTED_CSV
from app.domain.dimensions import CANONICAL_ACCOUNT_NAMES

UNIT_LABEL_DEFAULT = "KRW_MILLION"


class StatementFormatError(ValueError):
    pass


def read_wide_statement(path: Path) -> pl.DataFrame:
    """Returns long format: raw_account_name, year, amount."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pl.read_excel(path)
    elif suffix == ".csv":
        df = pl.read_csv(path)
    else:
        raise StatementFormatError(f"지원하지 않는 파일 형식입니다: {suffix} (xlsx, xls, csv만 가능)")

    if df.width < 2:
        raise StatementFormatError("파일에 계정과목 열과 최소 1개의 연도 열이 필요합니다.")

    account_col = df.columns[0]
    year_cols = [c for c in df.columns[1:] if str(c).strip().isdigit()]
    if not year_cols:
        raise StatementFormatError(
            "연도로 보이는 열 헤더를 찾지 못했습니다 (예: 2024, 2025). "
            "첫 번째 열은 계정과목, 나머지 열은 4자리 연도여야 합니다."
        )

    long_df = df.select([account_col] + year_cols).unpivot(
        index=account_col, on=year_cols, variable_name="year", value_name="amount"
    )
    long_df = long_df.rename({account_col: "raw_account_name"})
    long_df = long_df.filter(pl.col("amount").is_not_null())
    long_df = long_df.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("amount").cast(pl.Float64),
        pl.col("raw_account_name").cast(pl.Utf8).str.strip_chars(),
    )
    long_df = long_df.filter(pl.col("raw_account_name") != "")
    return long_df


@dataclass(frozen=True)
class AccountGroup:
    raw_account_name: str
    year_count: int
    mapping: AccountMapping


def group_by_account(long_df: pl.DataFrame) -> list[AccountGroup]:
    """One row per distinct raw account name, with its normalizer result —
    the unit of decision a user reviews before import (not per-year)."""
    groups = []
    for raw_name in long_df["raw_account_name"].unique(maintain_order=True).to_list():
        year_count = long_df.filter(pl.col("raw_account_name") == raw_name).height
        groups.append(AccountGroup(raw_name, year_count, normalize_account_name(raw_name)))
    return groups


def save_imported_facts(company: str, long_df: pl.DataFrame, account_code_by_raw_name: dict[str, str]) -> Path:
    """`account_code_by_raw_name` maps raw_account_name -> canonical code for
    every row the caller decided to keep (rows for excluded raw names should
    simply be absent from this dict, not mapped to a placeholder)."""
    rows = []
    for row in long_df.iter_rows(named=True):
        code = account_code_by_raw_name.get(row["raw_account_name"])
        if code is None:
            continue
        rows.append(
            {
                "company": company,
                "year": row["year"],
                "account_code": code,
                "account_name": CANONICAL_ACCOUNT_NAMES.get(code, code),
                "amount": row["amount"],
                "unit": UNIT_LABEL_DEFAULT,
            }
        )

    if not rows:
        raise StatementFormatError("가져올 데이터가 없습니다 (모든 계정이 제외되었습니다).")

    new_df = pl.DataFrame(rows)

    IMPORTED_CSV.parent.mkdir(parents=True, exist_ok=True)
    if IMPORTED_CSV.exists():
        existing = pl.read_csv(IMPORTED_CSV)
        key_cols = ["company", "year", "account_code"]
        existing = existing.join(new_df.select(key_cols), on=key_cols, how="anti")
        combined = pl.concat([existing, new_df])
    else:
        combined = new_df

    combined.write_csv(IMPORTED_CSV)
    return IMPORTED_CSV
