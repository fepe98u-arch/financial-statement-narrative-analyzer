from pathlib import Path

import polars as pl
import pytest

from app.data import statement_import as si
from app.data.cloud_sync_guard import detect_cloud_sync_marker


def _write_wide_csv(path: Path) -> None:
    path.write_text(
        "계정과목,2024,2025\n"
        "매출,100000,110000\n"
        "매출채권,12000,13000\n"
        "완전히 관련없는 임의계정XYZ,500,600\n",
        encoding="utf-8",
    )


def test_read_wide_statement_unpivots_to_long_format(tmp_path):
    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)

    long_df = si.read_wide_statement(csv_path)
    assert set(long_df.columns) == {"raw_account_name", "year", "amount"}
    assert long_df.height == 6  # 3 accounts x 2 years


def test_read_wide_statement_rejects_unsupported_extension(tmp_path):
    bad_path = tmp_path / "statement.txt"
    bad_path.write_text("nothing", encoding="utf-8")
    with pytest.raises(si.StatementFormatError):
        si.read_wide_statement(bad_path)


def test_read_wide_statement_requires_year_columns(tmp_path):
    csv_path = tmp_path / "no_years.csv"
    csv_path.write_text("계정과목,비고\n매출,100\n", encoding="utf-8")
    with pytest.raises(si.StatementFormatError):
        si.read_wide_statement(csv_path)


def test_group_by_account_resolves_known_names_and_flags_unknown(tmp_path):
    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)
    long_df = si.read_wide_statement(csv_path)
    groups = si.group_by_account(long_df)

    by_name = {g.raw_account_name: g for g in groups}
    assert by_name["매출"].mapping.canonical_account_code == "SALES"
    assert by_name["완전히 관련없는 임의계정XYZ"].mapping.canonical_account_code is None


def test_save_imported_facts_writes_only_selected_accounts(tmp_path, monkeypatch):
    target_csv = tmp_path / "imported_financials.csv"
    monkeypatch.setattr(si, "IMPORTED_CSV", target_csv)

    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)
    long_df = si.read_wide_statement(csv_path)

    si.save_imported_facts("테스트회사", long_df, {"매출": "SALES"})

    saved = pl.read_csv(target_csv)
    assert saved.height == 2  # 매출, 2 years
    assert set(saved["account_code"].to_list()) == {"SALES"}
    assert set(saved["company"].to_list()) == {"테스트회사"}


def test_save_imported_facts_overwrites_same_company_year_account(tmp_path, monkeypatch):
    target_csv = tmp_path / "imported_financials.csv"
    monkeypatch.setattr(si, "IMPORTED_CSV", target_csv)

    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)
    long_df = si.read_wide_statement(csv_path)

    si.save_imported_facts("테스트회사", long_df, {"매출": "SALES"})
    si.save_imported_facts("테스트회사", long_df, {"매출": "SALES"})  # re-import same data

    saved = pl.read_csv(target_csv)
    assert saved.height == 2  # not duplicated


def test_save_imported_facts_raises_when_nothing_selected(tmp_path, monkeypatch):
    target_csv = tmp_path / "imported_financials.csv"
    monkeypatch.setattr(si, "IMPORTED_CSV", target_csv)

    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)
    long_df = si.read_wide_statement(csv_path)

    with pytest.raises(si.StatementFormatError):
        si.save_imported_facts("테스트회사", long_df, {})


def test_cloud_sync_marker_detects_onedrive():
    assert detect_cloud_sync_marker(Path("C:/Users/x/OneDrive/project/data")) == "onedrive"


def test_cloud_sync_marker_none_for_normal_path():
    assert detect_cloud_sync_marker(Path("C:/Users/x/Documents/project/data")) is None


def test_build_raw_preview_table_needs_no_account_mapping(tmp_path):
    csv_path = tmp_path / "statement.csv"
    _write_wide_csv(csv_path)
    long_df = si.read_wide_statement(csv_path)

    wide, years = si.build_raw_preview_table(long_df)
    assert years == [2024, 2025]
    assert wide.height == 3  # all 3 raw accounts shown, including the unresolved one
    assert set(wide["raw_account_name"].to_list()) == {"매출", "매출채권", "완전히 관련없는 임의계정XYZ"}


def test_save_imported_facts_rejects_two_raw_names_mapped_to_same_account_year(tmp_path, monkeypatch):
    # Real DART filings can report the same concept under two different
    # labels for the same year (e.g. a subtotal line and a note-level
    # detail line) — both mapped to the same canonical account must not be
    # silently merged/overwritten.
    target_csv = tmp_path / "imported_financials.csv"
    monkeypatch.setattr(si, "IMPORTED_CSV", target_csv)

    long_df = pl.DataFrame(
        {
            "raw_account_name": ["매출채권", "매출채권및기타채권"],
            "year": [2025, 2025],
            "amount": [1000.0, 1200.0],
        }
    )

    with pytest.raises(si.StatementFormatError):
        si.save_imported_facts("테스트회사", long_df, {"매출채권": "RECEIVABLE", "매출채권및기타채권": "RECEIVABLE"})

    assert not target_csv.exists()
