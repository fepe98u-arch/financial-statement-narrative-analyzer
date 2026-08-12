"""Loads `.env` into the process environment once, at startup.

Hand-rolled (no extra dependency) — the same simple KEY=VALUE parsing
`app/db/connection.py` already used for DATABASE_URL, just applied to every
variable and actually written into `os.environ` so every module's plain
`os.environ.get(...)` calls (DART_API_KEY, NAVER_CLIENT_ID,
NAVER_CLIENT_SECRET, DATABASE_URL) can see it. Real environment variables
set outside `.env` always win (setdefault never overwrites them).
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

_loaded = False


def load_env_file() -> None:
    global _loaded
    if _loaded or not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
    _loaded = True
