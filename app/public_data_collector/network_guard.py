"""Network Guard (PROJECT_SPEC.md sections 36-38).

Every outbound payload must pass through `validate_outbound_request` right
before it would be sent. This is Allowlist-first (section 36) rather than a
blanket "reject anything with a number" regex (section 37 explicitly warns
against that, since dates/page numbers/corp_code are legitimate) — the
payload's *keys* are checked against a fixed allowlist, and its values are
checked against currently-configured secrets (section 38) as defense in
depth.
"""
from __future__ import annotations

import os

from app.public_data_collector.schemas import ALLOWED_OUTBOUND_FIELDS

# Env var names whose *values* must never appear in an outbound payload.
SECRET_ENV_VARS = ("DART_API_KEY", "DATABASE_URL", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")


class SecurityException(Exception):
    """Raised when an outbound request would violate the Private/Public
    boundary. Always fatal to that request — never caught-and-continued."""


def _check_allowlist(payload: dict) -> None:
    disallowed = set(payload.keys()) - ALLOWED_OUTBOUND_FIELDS
    if disallowed:
        raise SecurityException(
            f"Outbound request contains disallowed field(s): {sorted(disallowed)}. "
            f"Only {sorted(ALLOWED_OUTBOUND_FIELDS)} may leave this machine."
        )


def _check_secret_leakage(payload: dict) -> None:
    values_as_text = [str(v) for v in payload.values() if v is not None]
    for var in SECRET_ENV_VARS:
        secret_value = os.environ.get(var)
        if not secret_value:
            continue
        if any(secret_value in text for text in values_as_text):
            raise SecurityException(f"Outbound payload appears to contain the value of {var}.")


def validate_outbound_request(payload: dict) -> dict:
    _check_allowlist(payload)
    _check_secret_leakage(payload)
    return payload
