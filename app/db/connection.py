"""Local-only PostgreSQL connection (PROJECT_SPEC.md section 39).

No SQLite, no cloud Postgres. DATABASE_URL comes from `.env` and must point
at 127.0.0.1/localhost — this module refuses to build an engine for
anything else, so a cloud connection string can't slip in by accident.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/fsna"


class CloudDatabaseNotAllowedError(RuntimeError):
    pass


def _load_dotenv_value(key: str) -> str | None:
    """Minimal .env reader — avoids adding a dependency just for this."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return None


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or _load_dotenv_value("DATABASE_URL") or DEFAULT_DATABASE_URL


def _assert_local_host(database_url: str) -> None:
    host = urlparse(database_url.replace("postgresql+psycopg", "postgresql")).hostname
    if host not in ALLOWED_HOSTS:
        raise CloudDatabaseNotAllowedError(
            f"DATABASE_URL host '{host}' is not local. PROJECT_SPEC.md section 39 requires "
            "PostgreSQL to run on 127.0.0.1 only — cloud Postgres is not allowed in this project."
        )


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    _assert_local_host(url)
    return create_engine(url, pool_pre_ping=True)
