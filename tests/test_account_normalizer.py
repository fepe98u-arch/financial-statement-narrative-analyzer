from app.analysis.account_normalizer import MappingMethod, normalize_account_name


def test_exact_canonical_name_matches():
    result = normalize_account_name("매출채권")
    assert result.canonical_account_code == "RECEIVABLE"
    assert result.mapping_method == MappingMethod.EXACT
    assert result.mapping_confidence == 100.0


def test_known_synonym_matches_via_dictionary():
    result = normalize_account_name("외상매출금")
    assert result.canonical_account_code == "RECEIVABLE"
    assert result.mapping_method == MappingMethod.ACCOUNT_DICTIONARY


def test_close_variant_matches_via_fuzzy():
    result = normalize_account_name("매출채권및기타채권")
    assert result.canonical_account_code == "RECEIVABLE"


def test_unrecognizable_name_is_unresolved_not_guessed():
    result = normalize_account_name("완전히 알 수 없는 계정명 XYZ")
    assert result.mapping_method == MappingMethod.UNRESOLVED
    assert result.canonical_account_code is None


def test_loss_qualifier_suffix_is_stripped_before_exact_match():
    # DART convention: profit/income lines are labeled "X(손실)" to flag
    # they could be negative. Found via real LG Energy Solution data where
    # "당기순이익(손실)"/"영업이익(손실)" were falling through to a
    # 90.0-capped FUZZY match and getting excluded by the import UI.
    net_income = normalize_account_name("당기순이익(손실)")
    assert net_income.canonical_account_code == "NET_INCOME"
    assert net_income.mapping_method == MappingMethod.ACCOUNT_DICTIONARY
    assert net_income.mapping_confidence == 100.0

    operating_profit = normalize_account_name("영업이익(손실)")
    assert operating_profit.canonical_account_code == "OPERATING_PROFIT"
    assert operating_profit.mapping_method == MappingMethod.EXACT
    assert operating_profit.mapping_confidence == 100.0


def test_combined_tangible_assets_line_maps_to_its_own_code():
    # DART's summary statement (fnlttSinglAcntAll) reports 유형자산 as one
    # combined line, not broken into STRUCTURE/MACHINERY/CONSTRUCTION_IN_PROGRESS
    # — narrative_patterns.py's fallback clusters rely on this being mapped.
    result = normalize_account_name("유형자산")
    assert result.canonical_account_code == "TANGIBLE_ASSETS"
    assert result.mapping_method == MappingMethod.EXACT


def test_noncurrent_borrowings_synonym_maps_to_lt_borrowings():
    result = normalize_account_name("비유동성차입금")
    assert result.canonical_account_code == "LT_BORROWINGS"
    assert result.mapping_method == MappingMethod.ACCOUNT_DICTIONARY


def test_current_borrowings_does_not_false_positive_as_lt_borrowings():
    # "유동성차입금" (current/short-term portion) is a near-total substring
    # of "비유동성차입금" (added above as LT_BORROWINGS' synonym for the
    # long-term/non-current portion) — they mean opposite things but
    # differ by only one leading character, and rapidfuzz's WRatio scores
    # the pair ~92 (above the UI's >90.0 auto-accept line) despite that.
    result = normalize_account_name("유동성차입금")
    assert result.canonical_account_code is None
    assert result.mapping_method == MappingMethod.UNRESOLVED


def test_loss_qualifier_stripping_does_not_invent_matches_for_distinct_concepts():
    # "법인세비용차감전순이익" (profit before tax) is genuinely not the
    # same thing as net income — stripping "(손실)" must not promote it to
    # a confident ACCOUNT_DICTIONARY/EXACT match the way it correctly does
    # for "당기순이익(손실)". It can still surface as a low-stakes FUZZY
    # suggestion (for a human to review in the mapping table) — it just
    # must stay capped at the same 90.0 ceiling as any other coincidental
    # substring match, never treated as confirmed.
    result = normalize_account_name("법인세비용차감전순이익(손실)")
    assert result.mapping_method == MappingMethod.FUZZY
    assert result.mapping_confidence == 90.0
