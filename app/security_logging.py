"""Structured, allowlisted logging (PROJECT_SPEC.md section 43).

There is deliberately no "log this arbitrary string/message" function.
`log_event`'s signature only accepts the six fields section 43 permits —
timestamp, event_type, success, provider, error_code, records_count — so a
full financial statement, an investigation question, or an API key cannot
end up in the log file even by accident, because there's no parameter to
put them in.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / ".tmp" / "logs"
LOG_FILE = LOG_DIR / "security_events.log"

_logger = logging.getLogger("fsna.security")


def _ensure_configured() -> None:
    if _logger.handlers:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def log_event(
    event_type: str,
    success: bool,
    provider: str | None = None,
    error_code: str | None = None,
    records_count: int | None = None,
) -> None:
    _ensure_configured()
    entry = {
        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        "event_type": event_type,
        "success": success,
        "provider": provider,
        "error_code": error_code,
        "records_count": records_count,
    }
    _logger.info(json.dumps(entry, ensure_ascii=False))
