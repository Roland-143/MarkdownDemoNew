from __future__ import annotations

from ops_summary.db import load_sources_from_database
from ops_summary.reconcile import reconcile


def test_load_from_test_database_and_reconcile(initialized_test_database: str) -> None:
    production_df, shipping_df, inspection_df = load_sources_from_database(
        initialized_test_database
    )

    assert not production_df.empty
    assert not shipping_df.empty
    assert not inspection_df.empty

    result = reconcile(production_df, shipping_df, inspection_df)
    summary = result.summary

    assert len(summary) == 1

    row = summary.iloc[0]
    assert row["lot_code"] == "20260112001"
    assert row["ship_status"] == "shipped"
    assert int(row["total_defects"]) == 7
    assert row["top_defect_code"] == "CRACK"
    assert row["reconciliation_status"] == "reconciled"
