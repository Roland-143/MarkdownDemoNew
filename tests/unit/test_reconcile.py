from __future__ import annotations

import pandas as pd

from ops_summary.reconcile import reconcile


def test_reconcile_flags_priority_and_missing_sources() -> None:
    production_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001", "LOT-20260113-001"],
            "Date": ["2026-01-12", "2026-01-13"],
            "Production Line": ["Line 1", "Line 2"],
            "Units Planned": [400, 300],
            "Units Actual": [382, 298],
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

    result = reconcile(production_df, shipping_df, inspection_df)
    summary = result.summary

    top_row = summary.iloc[0]
    assert top_row["lot_code"] == "20260112001"
    assert bool(top_row["priority_lot"]) is True
    assert top_row["reconciliation_status"] == "reconciled"

    second_row = summary[summary["lot_code"] == "20260113001"].iloc[0]
    assert second_row["reconciliation_status"] == "missing_sources"
    assert bool(second_row["missing_shipping"]) is True
    assert bool(second_row["missing_inspection"]) is True


def test_reconcile_produces_traceability_payload() -> None:
    production_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Date": ["2026-01-12"],
            "Production Line": ["Line 1"],
            "Units Planned": [400],
            "Units Actual": [382],
        }
    )

    shipping_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Ship Date": ["2026-01-12"],
            "Qty Shipped": [390],
            "Ship Status": ["shipped"],
        }
    )

    inspection_df = pd.DataFrame(
        {
            "Lot ID": ["LOT-20260112-001"],
            "Inspection Date": ["2026-01-12"],
            "Defect Type": ["DENT"],
            "Defect Qty": [1],
        }
    )

    result = reconcile(production_df, shipping_df, inspection_df)

    trace_key = result.summary.iloc[0]["trace_key"]
    detail = result.details[trace_key]

    assert detail["reconciliation_basis"] == "lot + record_date"
    assert "qty_shipped_exceeds_units_actual" in detail["mismatch_notes"]
    assert len(detail["source_refs"]["production"]) == 1
    assert len(detail["source_refs"]["shipping"]) == 1
    assert len(detail["source_refs"]["inspection"]) == 1
