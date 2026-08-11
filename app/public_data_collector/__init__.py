"""The ONLY module in this project allowed to perform network I/O
(PROJECT_SPEC.md section 23). As of Phase 7 nothing here actually connects
to the internet yet — real providers arrive in Phase 8 (OpenDART) and
Phase 9 (news). Until then, `fake_provider.py` proves the request/response
shape end-to-end using local fixture data only.

Every file in this package must avoid importing private analysis objects
(FinancialStatement, DetectedPattern, InvestigationQuestion,
PrivateAnalysisResult, HumanReview) per section 22 — enforced by
tests/test_public_data_collector.py, not just by convention.
"""
