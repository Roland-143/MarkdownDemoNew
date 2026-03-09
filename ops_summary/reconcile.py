"""Core reconciliation engine for production, shipping, and inspection inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from ops_summary.normalize import canonicalize_lot, coerce_bool, coerce_date, coerce_int


VALID_SHIP_STATUSES = {
    "shipped",
    "partial",
    "on_hold",
    "backordered",
    "not_shipped",
    "unknown",
}

STATUS_PRIORITY = {
    "shipped": 5,
    "partial": 4,
    "on_hold": 3,
    "backordered": 2,
    "not_shipped": 1,
    "unknown": 0,
}


@dataclass(frozen=True)
class ReconcileResult:
    """Structured reconciliation output used by UI and tests."""

    summary: pd.DataFrame
    details: dict[str, dict[str, Any]]


def _empty_series(df: pd.DataFrame) -> pd.Series:
    return pd.Series([None] * len(df), index=df.index)


def _column_or_empty(df: pd.DataFrame, column_name: str) -> pd.Series:
    return df[column_name] if column_name in df.columns else _empty_series(df)


def _first_non_null(series: pd.Series) -> Any:
    for value in series.tolist():
        if value is not None and not pd.isna(value):
            return value
    return None


def _normalize_ship_status(raw_status: Any) -> str:
    if raw_status is None:
        return "unknown"

    normalized = str(raw_status).strip().lower().replace(" ", "_")
    return normalized if normalized in VALID_SHIP_STATUSES else "unknown"


def _detail_key(lot_code: str, record_date: date) -> str:
    return f"{lot_code}|{record_date.isoformat()}"


def _clean_production(production_df: pd.DataFrame | None) -> pd.DataFrame:
    df = production_df.copy() if production_df is not None else pd.DataFrame()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "lot_code",
                "record_date",
                "production_line",
                "part_number",
                "units_planned",
                "units_actual",
                "downtime_minutes",
                "line_issue_flag",
                "primary_issue",
                "raw_row",
            ]
        )

    prepared = pd.DataFrame(
        {
            "lot_code": _column_or_empty(df, "Lot ID").map(canonicalize_lot),
            "record_date": _column_or_empty(df, "Date").map(coerce_date),
            "production_line": _column_or_empty(df, "Production Line"),
            "part_number": _column_or_empty(df, "Part Number"),
            "units_planned": _column_or_empty(df, "Units Planned").map(coerce_int),
            "units_actual": _column_or_empty(df, "Units Actual").map(coerce_int),
            "downtime_minutes": _column_or_empty(df, "Downtime (min)").map(coerce_int),
            "line_issue_flag": _column_or_empty(df, "Line Issue?").map(coerce_bool),
            "primary_issue": _column_or_empty(df, "Primary Issue"),
            "raw_row": df.to_dict(orient="records"),
        }
    )

    return prepared.dropna(subset=["lot_code", "record_date"], how="any")


def _clean_shipping(shipping_df: pd.DataFrame | None) -> pd.DataFrame:
    df = shipping_df.copy() if shipping_df is not None else pd.DataFrame()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "lot_code",
                "record_date",
                "ship_date",
                "ship_status",
                "qty_shipped",
                "customer",
                "carrier",
                "raw_row",
            ]
        )

    prepared = pd.DataFrame(
        {
            "lot_code": _column_or_empty(df, "Lot ID").map(canonicalize_lot),
            "record_date": _column_or_empty(df, "Ship Date").map(coerce_date),
            "ship_date": _column_or_empty(df, "Ship Date").map(coerce_date),
            "ship_status": _column_or_empty(df, "Ship Status").map(
                _normalize_ship_status
            ),
            "qty_shipped": _column_or_empty(df, "Qty Shipped").map(coerce_int),
            "customer": _column_or_empty(df, "Customer"),
            "carrier": _column_or_empty(df, "Carrier"),
            "raw_row": df.to_dict(orient="records"),
        }
    )

    return prepared.dropna(subset=["lot_code", "record_date"], how="any")


def _clean_inspection(inspection_df: pd.DataFrame | None) -> pd.DataFrame:
    df = inspection_df.copy() if inspection_df is not None else pd.DataFrame()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "lot_code",
                "record_date",
                "defect_type",
                "defect_qty",
                "overall_result",
                "raw_row",
            ]
        )

    date_column = (
        "Inspection Date"
        if "Inspection Date" in df.columns
        else "Date"
        if "Date" in df.columns
        else "Ship Date"
    )

    prepared = pd.DataFrame(
        {
            "lot_code": _column_or_empty(df, "Lot ID").map(canonicalize_lot),
            "record_date": _column_or_empty(df, date_column).map(coerce_date),
            "defect_type": _column_or_empty(df, "Defect Type"),
            "defect_qty": _column_or_empty(df, "Defect Qty").map(coerce_int),
            "overall_result": _column_or_empty(df, "Overall Result"),
            "raw_row": df.to_dict(orient="records"),
        }
    )

    prepared["defect_qty"] = prepared["defect_qty"].fillna(0)
    prepared["defect_type"] = prepared["defect_type"].fillna("UNSPECIFIED")

    return prepared.dropna(subset=["lot_code", "record_date"], how="any")


def _aggregate_production(production: pd.DataFrame) -> pd.DataFrame:
    if production.empty:
        return pd.DataFrame(columns=["lot_code", "record_date", "production_count"])

    grouped = (
        production.groupby(["lot_code", "record_date"], as_index=False)
        .agg(
            production_line=("production_line", _first_non_null),
            part_number=("part_number", _first_non_null),
            units_planned=("units_planned", "sum"),
            units_actual=("units_actual", "sum"),
            downtime_minutes=("downtime_minutes", "sum"),
            line_issue_flag=("line_issue_flag", _first_non_null),
            primary_issue=("primary_issue", _first_non_null),
            production_count=("lot_code", "size"),
        )
        .reset_index(drop=True)
    )

    return grouped


def _aggregate_shipping(shipping: pd.DataFrame) -> pd.DataFrame:
    if shipping.empty:
        return pd.DataFrame(columns=["lot_code", "record_date", "shipping_count"])

    grouped = (
        shipping.groupby(["lot_code", "record_date"], as_index=False)
        .agg(
            ship_date=("ship_date", _first_non_null),
            ship_status=(
                "ship_status",
                lambda s: max(s.tolist(), key=lambda v: STATUS_PRIORITY.get(v, 0)),
            ),
            qty_shipped=("qty_shipped", "sum"),
            customer=("customer", _first_non_null),
            carrier=("carrier", _first_non_null),
            shipping_count=("lot_code", "size"),
        )
        .reset_index(drop=True)
    )

    return grouped


def _aggregate_inspection(inspection: pd.DataFrame) -> pd.DataFrame:
    if inspection.empty:
        return pd.DataFrame(columns=["lot_code", "record_date", "inspection_count"])

    grouped = (
        inspection.groupby(["lot_code", "record_date"], as_index=False)
        .agg(
            total_defects=("defect_qty", "sum"),
            inspection_count=("lot_code", "size"),
        )
        .reset_index(drop=True)
    )

    top_defects = (
        inspection.sort_values(
            ["lot_code", "record_date", "defect_qty", "defect_type"],
            ascending=[True, True, False, True],
        )
        .drop_duplicates(subset=["lot_code", "record_date"])[
            ["lot_code", "record_date", "defect_type"]
        ]
        .rename(columns={"defect_type": "top_defect_code"})
    )

    return grouped.merge(top_defects, how="left", on=["lot_code", "record_date"])


def _build_details(
    summary: pd.DataFrame,
    production: pd.DataFrame,
    shipping: pd.DataFrame,
    inspection: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}

    production_groups = {
        key: group["raw_row"].tolist()
        for key, group in production.groupby(["lot_code", "record_date"])
        if isinstance(key[1], date)
    }
    shipping_groups = {
        key: group["raw_row"].tolist()
        for key, group in shipping.groupby(["lot_code", "record_date"])
        if isinstance(key[1], date)
    }
    inspection_groups = {
        key: group["raw_row"].tolist()
        for key, group in inspection.groupby(["lot_code", "record_date"])
        if isinstance(key[1], date)
    }

    for row in summary.itertuples(index=False):
        key_tuple = (row.lot_code, row.record_date)
        detail_key = _detail_key(row.lot_code, row.record_date)
        missing_sources = []
        if row.missing_production:
            missing_sources.append("production")
        if row.missing_inspection:
            missing_sources.append("inspection")
        if row.missing_shipping:
            missing_sources.append("shipping")

        mismatch_notes = []
        if (
            row.units_actual is not None
            and row.qty_shipped is not None
            and row.qty_shipped > row.units_actual
        ):
            mismatch_notes.append("qty_shipped_exceeds_units_actual")

        insufficient_fields = []
        if row.units_planned is None:
            insufficient_fields.append("units_planned")
        if row.units_actual is None:
            insufficient_fields.append("units_actual")

        details[detail_key] = {
            "lot_code": row.lot_code,
            "record_date": row.record_date.isoformat(),
            "reconciliation_basis": "lot + record_date",
            "missing_sources": missing_sources,
            "insufficient_fields": insufficient_fields,
            "mismatch_notes": mismatch_notes,
            "source_refs": {
                "production": production_groups.get(key_tuple, []),
                "inspection": inspection_groups.get(key_tuple, []),
                "shipping": shipping_groups.get(key_tuple, []),
            },
        }

    return details


def reconcile(
    production_df: pd.DataFrame | None,
    shipping_df: pd.DataFrame | None,
    inspection_df: pd.DataFrame | None = None,
) -> ReconcileResult:
    """Reconcile source data on canonical lot + record_date."""
    production = _clean_production(production_df)
    shipping = _clean_shipping(shipping_df)
    inspection = _clean_inspection(inspection_df)

    production_rollup = _aggregate_production(production)
    shipping_rollup = _aggregate_shipping(shipping)
    inspection_rollup = _aggregate_inspection(inspection)

    key_frames = [
        frame[["lot_code", "record_date"]]
        for frame in [production_rollup, shipping_rollup, inspection_rollup]
        if not frame.empty
    ]

    if not key_frames:
        return ReconcileResult(summary=pd.DataFrame(), details={})

    keys = (
        pd.concat(key_frames, ignore_index=True)
        .drop_duplicates()
        .sort_values(["lot_code", "record_date"])
    )

    summary = keys.merge(
        production_rollup,
        how="left",
        on=["lot_code", "record_date"],
        indicator="_production_merge",
    )
    summary = summary.merge(
        inspection_rollup,
        how="left",
        on=["lot_code", "record_date"],
        indicator="_inspection_merge",
    )
    summary = summary.merge(
        shipping_rollup,
        how="left",
        on=["lot_code", "record_date"],
        indicator="_shipping_merge",
    )

    summary["missing_production"] = summary["_production_merge"] == "left_only"
    summary["missing_inspection"] = summary["_inspection_merge"] == "left_only"
    summary["missing_shipping"] = summary["_shipping_merge"] == "left_only"

    summary = summary.drop(
        columns=["_production_merge", "_inspection_merge", "_shipping_merge"]
    )

    summary["ship_status"] = summary["ship_status"].fillna("unknown")
    summary["priority_lot"] = summary["ship_status"].isin(["shipped", "partial"]) & (
        summary["total_defects"].fillna(0) > 0
    )

    summary["source_ref_count"] = (
        (~summary["missing_production"]).astype(int)
        + (~summary["missing_inspection"]).astype(int)
        + (~summary["missing_shipping"]).astype(int)
    )

    def _status(row: pd.Series) -> str:
        if (
            row["missing_production"]
            and row["missing_inspection"]
            and row["missing_shipping"]
        ):
            return "insufficient_data"
        if (
            row["missing_production"]
            or row["missing_inspection"]
            or row["missing_shipping"]
        ):
            return "missing_sources"
        return "reconciled"

    summary["reconciliation_status"] = summary.apply(_status, axis=1)

    def _reason(row: pd.Series) -> str:
        missing = []
        if row["missing_production"]:
            missing.append("production")
        if row["missing_inspection"]:
            missing.append("inspection")
        if row["missing_shipping"]:
            missing.append("shipping")
        if missing:
            return "missing_" + "_".join(missing)
        return "ok"

    summary["status_reason"] = summary.apply(_reason, axis=1)
    summary["trace_key"] = summary.apply(
        lambda row: _detail_key(row["lot_code"], row["record_date"]), axis=1
    )

    summary = summary.sort_values(
        by=["priority_lot", "total_defects", "record_date", "lot_code"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    details = _build_details(summary, production, shipping, inspection)

    return ReconcileResult(summary=summary, details=details)
