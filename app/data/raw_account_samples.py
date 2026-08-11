"""Synthetic raw account-name labels for demoing the Account Normalizer.

Stands in for "this year's trial balance used slightly different labels
than last year's" (PROJECT_SPEC.md section 10). Not tied to any real
filing.
"""

RAW_ACCOUNT_NAME_SAMPLES: list[str] = [
    "매출",
    "매출채권",
    "매출채권및기타채권",
    "외상매출금",
    "재고자산",
    "재고자산(상품)",
    "구축물",
    "구축물(순액)",
    "기계장치",
    "장기차입금",
    "장기차입금(원화)",
    "영업활동현금흐름",
    "당기순이익",
    "대손충당금",
    "자산총계",
    "임원 개인 대여금",  # deliberately unrelated — should end up UNRESOLVED
]
