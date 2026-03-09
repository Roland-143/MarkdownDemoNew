"""Environment-backed app configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_environment(*, test: bool = False, override: bool = False) -> None:
    """Load .env and optionally .env.test into process environment."""
    load_dotenv(ROOT_DIR / ".env", override=False)
    if test:
        load_dotenv(ROOT_DIR / ".env.test", override=override)


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    test_database_url: str | None
    auto_load_db_on_start: bool


def _as_bool(raw_value: str | None) -> bool:
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_settings(*, test: bool = False) -> Settings:
    """Resolve settings from loaded environment variables."""
    load_environment(test=test)
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        test_database_url=os.getenv("TEST_DATABASE_URL"),
        auto_load_db_on_start=_as_bool(os.getenv("AUTO_LOAD_DB_ON_START")),
    )
