"""Fetch actual financial statement figures from OpenDART, as an
alternative to the manual Excel copy-paste flow.

This is still "public data collection" in PROJECT_SPEC.md's sense: a
company's filed financial statements are public record the moment DART
publishes them (the same numbers a person could copy off the DART website
by hand). What goes OUT to DART here is only corp_code/bsns_year/
reprt_code/fs_div — DART-required technical parameters (section 2). What
comes IN becomes this app's own financial_facts once imported, at which
point it's protected like any other private analysis input from then on.

Two DART endpoints are used:
- corpCode.xml: bulk company-name -> corp_code lookup (a ~1.5MB zip),
  cached locally since it changes rarely.
- fnlttSinglAcntAll.json: one company's full reported account list for one
  (bsns_year, reprt_code, fs_div) — conveniently returns THREE periods per
  call (당기/전기/전전기), so a handful of calls covers several years.
"""
from __future__ import annotations

import io
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

from app.security_logging import log_event

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORP_CODE_CACHE = PROJECT_ROOT / ".tmp" / "dart_corp_codes.json"

CORP_CODE_ENDPOINT = "https://opendart.fss.or.kr/api/corpCode.xml"
FINANCIAL_STATEMENT_ENDPOINT = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

REPORT_CODE_ANNUAL = "11011"
NO_DATA_STATUS = "013"  # OpenDART's "조회된 데이터가 없습니다" status code

# sj_div -> display label. The same account_nm can legitimately appear in
# more than one of these (e.g. "매출채권" as a balance-sheet balance AND
# again as a cash-flow-statement working-capital delta) — every merge/group
# operation below keys on (account_nm, sj_div) together, never account_nm
# alone, so those never get conflated.
STATEMENT_SECTION_LABELS = {
    "BS": "재무상태표",
    "IS": "손익계산서",
    "CIS": "포괄손익계산서",
    "CF": "현금흐름표",
    "SCE": "자본변동표",
}


class MissingCredentialError(RuntimeError):
    pass


def _require_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("DART_API_KEY")
    if not key:
        raise MissingCredentialError(
            "DART_API_KEY is not set. Get a free key at https://opendart.fss.or.kr/ "
            "and add DART_API_KEY=... to .env."
        )
    return key


def _download_corp_codes(api_key: str, timeout_seconds: float = 30.0) -> list[dict]:
    response = requests.get(CORP_CODE_ENDPOINT, params={"crtfc_key": api_key}, timeout=timeout_seconds)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_bytes)
    corps = [
        {
            "corp_code": (el.findtext("corp_code") or "").strip(),
            "corp_name": (el.findtext("corp_name") or "").strip(),
            "stock_code": (el.findtext("stock_code") or "").strip(),
        }
        for el in root.findall("list")
    ]
    log_event("PUBLIC_DATA_FETCH", success=True, provider="dart-corpcode", records_count=len(corps))
    return corps


def get_corp_codes(api_key: str | None = None, force_refresh: bool = False) -> list[dict]:
    """Cached locally (public reference data, not sensitive) so this ~1.5MB
    download only happens when the cache is missing or explicitly refreshed."""
    if not force_refresh and CORP_CODE_CACHE.exists():
        return json.loads(CORP_CODE_CACHE.read_text(encoding="utf-8"))

    key = _require_api_key(api_key)
    corps = _download_corp_codes(key)
    CORP_CODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CORP_CODE_CACHE.write_text(json.dumps(corps, ensure_ascii=False), encoding="utf-8")
    return corps


def search_corp_codes(query: str, api_key: str | None = None, listed_only: bool = True, limit: int = 20) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    corps = get_corp_codes(api_key)
    matches = [c for c in corps if query in c["corp_name"]]
    if listed_only:
        matches = [c for c in matches if c["stock_code"]]
    return matches[:limit]


def _fetch_one_statement(api_key: str, corp_code: str, bsns_year: str, reprt_code: str, fs_div: str, timeout_seconds: float) -> list[dict]:
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
    }
    response = requests.get(FINANCIAL_STATEMENT_ENDPOINT, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    data = response.json()

    if data.get("status") == NO_DATA_STATUS:
        return []
    if data.get("status") != "000":
        raise RuntimeError(f"OpenDART API error {data.get('status')}: {data.get('message')}")
    return data.get("list", [])


def _fetch_with_cfs_ofs_fallback(api_key: str, corp_code: str, bsns_year: str, reprt_code: str, fs_div: str, timeout_seconds: float) -> list[dict]:
    items = _fetch_one_statement(api_key, corp_code, bsns_year, reprt_code, fs_div, timeout_seconds)
    if not items and fs_div == "CFS":
        # Many companies with no subsidiaries never file a separate
        # consolidated statement — fall back to 개별(OFS) rather than
        # reporting "no data".
        items = _fetch_one_statement(api_key, corp_code, bsns_year, reprt_code, "OFS", timeout_seconds)
    return items


def _transform_to_long_rows(statement_items: list[dict], bsns_year: str) -> list[dict]:
    """One DART call returns 당기/전기/전전기 together — expand that into
    our long format: raw_account_name, year, amount, sj_div, sj_nm, ord.
    sj_div/ord are kept specifically so a later step can (a) never merge
    same-named accounts from different statements and (b) can group/sort
    each statement separately, matching how DART itself presents them."""
    base_year = int(bsns_year)
    period_years = {"thstrm_amount": base_year, "frmtrm_amount": base_year - 1, "bfefrmtrm_amount": base_year - 2}

    rows = []
    for item in statement_items:
        account_name = (item.get("account_nm") or "").strip()
        if not account_name:
            continue
        sj_div = (item.get("sj_div") or "").strip()
        sj_nm = (item.get("sj_nm") or "").strip() or STATEMENT_SECTION_LABELS.get(sj_div, sj_div or "기타")
        try:
            order = int(item.get("ord") or 0)
        except ValueError:
            order = 0

        for amount_field, year in period_years.items():
            raw_amount = item.get(amount_field)
            if not raw_amount:
                continue
            try:
                amount = float(str(raw_amount).replace(",", ""))
            except ValueError:
                continue
            rows.append(
                {
                    "raw_account_name": account_name,
                    "year": year,
                    "amount": amount,
                    "sj_div": sj_div,
                    "sj_nm": sj_nm,
                    "account_order": order,
                }
            )
    return rows


def anchors_for_years(latest_year: int, num_years: int) -> list[int]:
    """bsns_year values to call so that every year in
    [latest_year - num_years + 1, latest_year] is covered by at least one
    call's 당기/전기/전전기 (each call covers 3 consecutive years)."""
    earliest = latest_year - num_years + 1
    anchors = []
    year = latest_year
    while year >= earliest:
        anchors.append(year)
        year -= 3
    return anchors


def fetch_financial_statement_rows(
    corp_code: str,
    latest_year: int,
    num_years: int,
    api_key: str | None = None,
    fs_div: str = "CFS",
    reprt_code: str = REPORT_CODE_ANNUAL,
    timeout_seconds: float = 15.0,
) -> list[dict]:
    """Returns long-format rows (raw_account_name, year, amount, sj_div,
    sj_nm, account_order) ready for the same account-mapping preview the
    Excel import flow uses. Rows are merged by (name, year, sj_div) — never
    by name alone — so a balance-sheet balance and a cash-flow-statement
    delta that happen to share a label never overwrite each other."""
    key = _require_api_key(api_key)
    earliest_year = latest_year - num_years + 1

    combined: dict[tuple[str, int, str], dict] = {}
    try:
        for anchor in sorted(anchors_for_years(latest_year, num_years)):  # oldest first: newest anchor wins on overlap
            items = _fetch_with_cfs_ofs_fallback(key, corp_code, str(anchor), reprt_code, fs_div, timeout_seconds)
            for row in _transform_to_long_rows(items, str(anchor)):
                combined[(row["raw_account_name"], row["year"], row["sj_div"])] = row
    except (requests.RequestException, RuntimeError) as exc:
        log_event("PUBLIC_DATA_FETCH", success=False, provider="dart-financials", error_code=type(exc).__name__)
        raise

    rows = [row for row in combined.values() if earliest_year <= row["year"] <= latest_year]
    log_event("PUBLIC_DATA_FETCH", success=True, provider="dart-financials", records_count=len(rows))
    return rows
