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
