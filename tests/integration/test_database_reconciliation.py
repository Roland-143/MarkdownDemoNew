from __future__ import annotations

import logging

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


def test_load_sources_logs_row_counts(initialized_test_database: str, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="ops_summary.db"):
        production_df, shipping_df, inspection_df = load_sources_from_database(
            initialized_test_database
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Loading reconciliation source data from database" in message
        for message in messages
    )
    assert "Loaded source data rows: production=1 shipping=1 inspection=1" in messages

    assert len(production_df) == 1
    assert len(shipping_df) == 1
    assert len(inspection_df) == 1
