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


def rows_to_long_df(rows: list[dict]) -> pl.DataFrame:
    """Same long format (raw_account_name, year, amount) from a plain list
    of dicts — the shape app/public_data_collector/dart_financials.py
    returns, so DART-sourced rows go through the exact same mapping-preview
    and save path as a file import."""
    if not rows:
        raise StatementFormatError("가져올 데이터가 없습니다.")
    return pl.DataFrame(rows).with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("amount").cast(pl.Float64),
        pl.col("raw_account_name").cast(pl.Utf8).str.strip_chars(),
    )


def build_raw_preview_table(long_df: pl.DataFrame) -> tuple[pl.DataFrame, list[int]]:
    """Pivots raw (unmapped) long-format data into one row per raw account
    name, one column per year — a plain read-only view of exactly what was
    fetched/loaded, no Account Normalizer involved. Lets a user just look
    at the statement without needing every line item to map onto this
    app's ~15-account analysis schema."""
    years = sorted(int(y) for y in long_df["year"].unique().to_list())
    order = long_df["raw_account_name"].unique(maintain_order=True).to_list()

    wide = long_df.pivot(values="amount", index="raw_account_name", on="year")
    order_df = pl.DataFrame({"raw_account_name": order, "_order": list(range(len(order)))})
    wide = wide.join(order_df, on="raw_account_name", how="inner").sort("_order").drop("_order")
    return wide, years


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
    simply be absent from this dict, not mapped to a placeholder).

    Real filings sometimes report the same concept under two different raw
    labels (e.g. a subtotal line named identically to a note-level detail
    line) that both get mapped to the same canonical account — rather than
    silently keeping one and dropping the other, that's surfaced as an
    error so the user picks which raw label to keep (section 10's "don't
    silently resolve ambiguity", applied to this collision too).
    """
    rows = []
    claimed_by: dict[tuple[int, str], str] = {}  # (year, account_code) -> raw_account_name
    conflicts: set[str] = set()

    for row in long_df.iter_rows(named=True):
        raw_name = row["raw_account_name"]
        code = account_code_by_raw_name.get(raw_name)
        if code is None:
            continue

        key = (row["year"], code)
        existing_raw_name = claimed_by.get(key)
        if existing_raw_name is not None and existing_raw_name != raw_name:
            account_label = CANONICAL_ACCOUNT_NAMES.get(code, code)
            conflicts.add(f"{row['year']}년 {account_label}: '{existing_raw_name}' vs '{raw_name}'")
            continue
        claimed_by[key] = raw_name

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

    if conflicts:
        raise StatementFormatError(
            "같은 표준계정으로 매핑된 서로 다른 원본 항목이 있습니다. 매핑 화면에서 하나만 남기고 "
            "나머지는 '(제외 - 가져오지 않음)'으로 바꿔주세요:\n" + "\n".join(sorted(conflicts))
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
