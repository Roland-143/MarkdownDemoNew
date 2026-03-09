from __future__ import annotations

from ops_summary.normalize import canonicalize_lot, coerce_bool, coerce_date, coerce_int


def test_canonicalize_lot_handles_format_variants() -> None:
    assert canonicalize_lot("Lot-20260112-001") == "20260112001"
    assert canonicalize_lot("LOT 20260112 001") == "20260112001"
    assert canonicalize_lot("L0T_20260112-001") == "20260112001"


def test_canonicalize_lot_rejects_empty_inputs() -> None:
    assert canonicalize_lot(None) is None
    assert canonicalize_lot("") is None
    assert canonicalize_lot("   ") is None


def test_coercion_helpers() -> None:
    assert coerce_int("42") == 42
    assert coerce_int("x") is None
    assert coerce_bool("Yes") is True
    assert coerce_bool("0") is False
    parsed = coerce_date("2026-01-12")
    assert parsed is not None
    assert parsed.isoformat() == "2026-01-12"
