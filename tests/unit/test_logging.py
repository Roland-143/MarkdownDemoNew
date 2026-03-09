from __future__ import annotations

import logging

import pandas as pd

from ops_summary.reconcile import reconcile


def test_reconcile_logs_start_and_completion(caplog) -> None:
    production_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Date": ["2026-01-12"],
            "Units Planned": [400],
            "Units Actual": [382],
        }
    )
    shipping_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Ship Date": ["2026-01-12"],
            "Qty Shipped": [380],
            "Ship Status": ["shipped"],
        }
    )
    inspection_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Inspection Date": ["2026-01-12"],
            "Defect Type": ["CRACK"],
            "Defect Qty": [7],
        }
    )

    with caplog.at_level(logging.INFO, logger="ops_summary.reconcile"):
        reconcile(production_df, shipping_df, inspection_df)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Starting reconciliation with raw rows: production=1 shipping=1 inspection=1"
        in message
        for message in messages
    )
    assert any(
        "Reconciliation complete: summary_rows=1 priority_rows=1 missing_sources_rows=0"
        in message
        for message in messages
    )


def test_reconcile_logs_empty_input_result(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="ops_summary.reconcile"):
        result = reconcile(None, None, None)

    assert result.summary.empty
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "No valid lot/date keys found; returning empty reconciliation result" in message
        for message in messages
    )
