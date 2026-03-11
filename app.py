"""Streamlit app for operational summary reconciliation."""

from __future__ import annotations

import logging
import os
import pandas as pd
import sentry_sdk
import streamlit as st

from ops_summary.config import get_settings
from ops_summary.db import load_sources_from_database
from ops_summary.reconcile import ReconcileResult, reconcile


st.set_page_config(page_title="Operational Summary Reconciler", layout="wide")
logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        send_default_pii=False,
        traces_sample_rate=0.0,
        enable_logs=False,
        http_proxy="",
        https_proxy="",
    )


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _read_csv(uploaded_file: object | None) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    return pd.read_csv(uploaded_file)


def _empty_result() -> ReconcileResult:
    return ReconcileResult(summary=pd.DataFrame(), details={})


def _format_trace_option(trace_key: str) -> str:
    lot_code, record_date = trace_key.split("|")
    return f"Lot {lot_code} @ {record_date}"


def _apply_filters(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary

    filtered = summary.copy()

    st.sidebar.markdown("### Filters")
    lot_query = st.sidebar.text_input("Lot contains", value="").strip()
    if lot_query:
        filtered = filtered[
            filtered["lot_code"].str.contains(lot_query, case=False, na=False)
        ]

    record_dates = filtered["record_date"].dropna()
    if not record_dates.empty:
        min_date = record_dates.min()
        max_date = record_dates.max()
        selected_range = st.sidebar.date_input(
            "Record date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start_date, end_date = selected_range
            filtered = filtered[
                (filtered["record_date"] >= start_date)
                & (filtered["record_date"] <= end_date)
            ]

    ship_status_options = sorted(filtered["ship_status"].dropna().unique().tolist())
    selected_statuses = st.sidebar.multiselect(
        "Ship status",
        options=ship_status_options,
        default=ship_status_options,
    )
    if selected_statuses:
        filtered = filtered[filtered["ship_status"].isin(selected_statuses)]

    defect_type = st.sidebar.text_input("Top defect code", value="").strip()
    if defect_type:
        filtered = filtered[
            filtered["top_defect_code"]
            .fillna("")
            .str.contains(defect_type, case=False, na=False)
        ]

    production_line = st.sidebar.text_input("Production line", value="").strip()
    if production_line:
        filtered = filtered[
            filtered["production_line"]
            .fillna("")
            .str.contains(production_line, case=False, na=False)
        ]

    return filtered.reset_index(drop=True)


def _render_summary(result: ReconcileResult) -> None:
    summary = result.summary
    if summary.empty:
        st.info("Load source data to generate the operational summary.")
        return

    filtered = _apply_filters(summary)

    total_rows = len(filtered)
    incomplete_rows = int((filtered["reconciliation_status"] != "reconciled").sum())
    priority_rows = int(filtered["priority_lot"].sum())

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Visible rows", total_rows)
    metric_col2.metric("Incomplete rows", incomplete_rows)
    metric_col3.metric("Priority rows", priority_rows)

    if not filtered.empty:
        st.caption(f"First visible lot: {filtered.iloc[0]['lot_code']}")

    display_columns = [
        "lot_code",
        "record_date",
        "production_line",
        "units_planned",
        "units_actual",
        "total_defects",
        "top_defect_code",
        "ship_status",
        "ship_date",
        "qty_shipped",
        "reconciliation_status",
        "status_reason",
        "source_ref_count",
        "priority_lot",
    ]

    display = filtered[display_columns].rename(
        columns={
            "lot_code": "Lot ID",
            "record_date": "Record Date",
            "production_line": "Production Line",
            "units_planned": "Units Planned",
            "units_actual": "Units Actual",
            "total_defects": "Total Defects",
            "top_defect_code": "Top Defect",
            "ship_status": "Ship Status",
            "ship_date": "Ship Date",
            "qty_shipped": "Qty Shipped",
            "reconciliation_status": "Reconciliation Status",
            "status_reason": "Status Reason",
            "source_ref_count": "Source Count",
            "priority_lot": "Priority",
        }
    )

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### Drill-down and Traceability")
    trace_options = filtered["trace_key"].tolist()
    selected_trace = st.selectbox(
        "Select a summary row",
        options=trace_options,
        format_func=_format_trace_option,
    )

    if selected_trace:
        st.json(result.details.get(selected_trace, {}), expanded=False)


def _run_upload_mode() -> None:
    st.markdown("### Upload CSVs")
    st.caption("Upload production + shipping CSVs. Inspection CSV is optional.")

    production_file = st.file_uploader(
        "Production CSV", type=["csv"], key="production_csv"
    )
    shipping_file = st.file_uploader("Shipping CSV", type=["csv"], key="shipping_csv")
    inspection_file = st.file_uploader(
        "Inspection CSV (optional)", type=["csv"], key="inspection_csv"
    )

    if st.button("Reconcile uploaded files", type="primary"):
        production_df = _read_csv(production_file)
        shipping_df = _read_csv(shipping_file)
        inspection_df = _read_csv(inspection_file)

        if production_df.empty and shipping_df.empty and inspection_df.empty:
            logger.warning("Upload reconcile requested without any CSV input")
            st.warning("Upload at least one CSV before reconciling.")
            return

        result = reconcile(production_df, shipping_df, inspection_df)
        st.session_state["result"] = result
        logger.info(
            "Upload reconcile completed with summary_rows=%s",
            len(result.summary),
        )


def _resolve_db_url(
    settings_database_url: str | None,
    settings_test_url: str | None,
    *,
    prefer_test: bool = False,
) -> str:
    if prefer_test and settings_test_url:
        return settings_test_url
    if settings_database_url:
        return settings_database_url
    if settings_test_url:
        return settings_test_url
    return ""


def _run_db_mode(auto_load: bool) -> None:
    st.markdown("### Connect to DB")

    settings = get_settings()
    db_url = _resolve_db_url(
        settings.database_url,
        settings.test_database_url,
        prefer_test=auto_load,
    )

    manual_db_url = st.text_input("Database URL", value=db_url, type="password")
    should_load = auto_load or st.button("Load from database", type="primary")

    if should_load:
        if not manual_db_url:
            logger.error("DB load requested without a database URL")
            st.error(
                "Provide DATABASE_URL or TEST_DATABASE_URL before loading from DB."
            )
            return

        production_df, shipping_df, inspection_df = load_sources_from_database(
            manual_db_url
        )
        result = reconcile(production_df, shipping_df, inspection_df)
        st.session_state["result"] = result
        logger.info("DB reconcile completed with summary_rows=%s", len(result.summary))


def main() -> None:
    _configure_logging()
    settings = get_settings()
    _init_sentry()

    if "result" not in st.session_state:
        st.session_state["result"] = _empty_result()

    st.title("Operational Summary Reconciler")
    st.write(
        "Align production, inspection, and shipping by canonical lot + date, then drill into source traces."
    )

    default_mode_index = 1 if settings.auto_load_db_on_start else 0
    mode = st.sidebar.radio(
        "Data source", ["Upload CSVs", "Connect to DB"], index=default_mode_index
    )

    if mode == "Upload CSVs":
        _run_upload_mode()
    else:
        _run_db_mode(auto_load=settings.auto_load_db_on_start)

    _render_summary(st.session_state["result"])


if __name__ == "__main__":
    main()
