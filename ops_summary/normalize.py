"""Normalization helpers for imported operations records."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd


LOT_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def canonicalize_lot(raw_lot: Any) -> str | None:
    """Convert a raw lot identifier into a canonical matching key."""
    if raw_lot is None:
        return None

    normalized = str(raw_lot).strip().upper()
    if not normalized:
        return None

    normalized = normalized.replace("L0T", "LOT")
    normalized = LOT_NON_ALNUM_RE.sub("", normalized)

    if normalized.startswith("LOT"):
        normalized = normalized[3:]

    return normalized or None


def coerce_date(value: Any) -> date | None:
    """Parse date-like values; invalid inputs return None."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def coerce_int(value: Any) -> int | None:
    """Parse integer-like values; invalid inputs return None."""
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return int(parsed)


def coerce_bool(value: Any) -> bool | None:
    """Parse common boolean-like values; invalid inputs return None."""
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False
    return None
