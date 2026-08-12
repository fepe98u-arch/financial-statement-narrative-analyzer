import os

import pytest

from app.public_data_collector import dart_financials as df


def test_anchors_for_years_covers_the_full_requested_range():
    anchors = df.anchors_for_years(latest_year=2025, num_years=5)
    covered_years = set()
    for anchor in anchors:
        covered_years.update({anchor, anchor - 1, anchor - 2})
    assert {2021, 2022, 2023, 2024, 2025} <= covered_years


def test_anchors_for_years_minimizes_calls():
    # 5 years should need at most 2 calls (each call covers 3 years)
    assert len(df.anchors_for_years(latest_year=2025, num_years=5)) <= 2


def test_transform_to_long_rows_expands_three_periods_per_item():
    items = [
        {
            "account_nm": "매출액",
            "thstrm_amount": "110,000",
            "frmtrm_amount": "100,000",
            "bfefrmtrm_amount": "90,000",
        }
    ]
    rows = df._transform_to_long_rows(items, "2025")
    by_year = {r["year"]: r["amount"] for r in rows}
    assert by_year == {2025: 110000.0, 2024: 100000.0, 2023: 90000.0}


def test_transform_to_long_rows_skips_blank_or_unparseable_amounts():
    items = [{"account_nm": "매출액", "thstrm_amount": "", "frmtrm_amount": "-", "bfefrmtrm_amount": "90000"}]
    rows = df._transform_to_long_rows(items, "2025")
    assert len(rows) == 1
    assert rows[0]["year"] == 2023


def test_transform_to_long_rows_skips_items_without_account_name():
    items = [{"account_nm": "", "thstrm_amount": "1000"}]
    assert df._transform_to_long_rows(items, "2025") == []


def test_transform_to_long_rows_keeps_sj_div_and_label():
    items = [{"account_nm": "매출채권", "thstrm_amount": "1000", "sj_div": "BS", "sj_nm": "재무상태표", "ord": "5"}]
    rows = df._transform_to_long_rows(items, "2025")
    assert rows[0]["sj_div"] == "BS"
    assert rows[0]["sj_nm"] == "재무상태표"
    assert rows[0]["account_order"] == 5


def test_fetch_does_not_merge_same_name_across_different_statements(monkeypatch):
    # The real-world bug: "매출채권" as a balance-sheet balance (BS) and
    # "매출채권" as a cash-flow working-capital delta (CF) must both survive
    # — previously the later one silently overwrote the earlier one.
    def fake_fetch(api_key, corp_code, bsns_year, reprt_code, fs_div, timeout_seconds):
        return [
            {"account_nm": "매출채권", "sj_div": "BS", "sj_nm": "재무상태표", "thstrm_amount": "500000"},
            {"account_nm": "매출채권", "sj_div": "CF", "sj_nm": "현금흐름표", "thstrm_amount": "-12000"},
        ]

    monkeypatch.setattr(df, "_fetch_with_cfs_ofs_fallback", fake_fetch)
    rows = df.fetch_financial_statement_rows("00000000", latest_year=2025, num_years=1, api_key="dummy-key")

    by_section = {r["sj_div"]: r["amount"] for r in rows}
    assert by_section == {"BS": 500000.0, "CF": -12000.0}


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    with pytest.raises(df.MissingCredentialError):
        df.get_corp_codes(api_key=None, force_refresh=True)


def test_live_corp_code_search_or_skip():
    if not os.environ.get("DART_API_KEY"):
        pytest.skip("DART_API_KEY not set")
    matches = df.search_corp_codes("삼성전자")
    assert any(m["corp_name"] == "삼성전자" for m in matches)


def test_live_financial_statement_fetch_or_skip():
    if not os.environ.get("DART_API_KEY"):
        pytest.skip("DART_API_KEY not set")
    matches = df.search_corp_codes("삼성전자")
    corp_code = next(m["corp_code"] for m in matches if m["corp_name"] == "삼성전자")

    rows = df.fetch_financial_statement_rows(corp_code, latest_year=2024, num_years=2)
    assert rows
    account_names = {r["raw_account_name"] for r in rows}
    assert any("매출" in name or "수익" in name for name in account_names)
