"""Small local, non-secret settings file (e.g. where the user's Local AI
model folder lives). Not the same thing as `.env` — nothing here is a
credential. Machine-specific, so it's gitignored like `.env`."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "app_settings.json"


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def get_local_ai_model_path() -> str | None:
    return load_settings().get("local_ai_model_path")


def set_local_ai_model_path(path: str) -> None:
    settings = load_settings()
    settings["local_ai_model_path"] = path
    save_settings(settings)
