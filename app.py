"""Streamlit app for operational summary reconciliation."""

from __future__ import annotations

from datetime import date, datetime
import logging
import os
from typing import Literal

import pandas as pd
import sentry_sdk
import streamlit as st

from ops_summary.config import get_settings
from ops_summary.db import load_sources_from_database
from ops_summary.reconcile import reconcile


TimeGrouping = Literal["Daily", "Weekly", "Monthly"]

st.set_page_config(
    page_title="Operational Signal Dashboard",
    page_icon=":material/insights:",
    layout="wide",
)
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


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f4f8fc;
            --surface: #ffffff;
            --surface-muted: #f7fafc;
            --line: #d7e2ee;
            --text: #132736;
            --text-muted: #516b7d;
            --accent: #0d6e9f;
            --accent-soft: #e4f2fb;
            --good: #176546;
            --good-soft: #e6f6ed;
            --warn: #8d5a11;
            --warn-soft: #fdf2dd;
            --risk: #8b2d2d;
            --risk-soft: #fde8e8;
        }
        .stApp {
            background:
                radial-gradient(1100px 420px at 8% -15%, #dfefff 0%, rgba(223,239,255,0) 62%),
                radial-gradient(980px 360px at 95% -18%, #d8f6f2 0%, rgba(216,246,242,0) 60%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
            color: var(--text);
        }
        section[data-testid="stSidebar"] {
            background: #102535;
            border-right: 1px solid #1c3a52;
        }
        section[data-testid="stSidebar"] * {
            color: #e9f3fa;
        }
        .shell-title {
            font-family: "Avenir Next", "Gill Sans", "Segoe UI", sans-serif;
            color: #f7fbff;
            font-size: 1.25rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: 0.02em;
        }
        .shell-subtitle {
            color: #b8d6ea;
            font-size: 0.82rem;
            margin: 0.1rem 0 0.9rem 0;
        }
        .shell-meta {
            margin-top: 0.9rem;
            padding: 0.7rem 0.75rem;
            border: 1px solid #2c4f68;
            border-radius: 10px;
            background: #0f2b40;
            font-size: 0.78rem;
            line-height: 1.45;
            color: #cfe7f7;
        }
        .page-title {
            font-family: "Avenir Next", "Gill Sans", "Segoe UI", sans-serif;
            color: var(--text);
            font-size: 2.45rem;
            font-weight: 820;
            letter-spacing: -0.02em;
            margin: 0;
            line-height: 1.03;
        }
        .page-subtitle {
            color: var(--text-muted);
            font-size: 1rem;
            margin-top: 0.35rem;
            margin-bottom: 0;
        }
        .status-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 0.26rem 0.75rem;
            background: var(--accent-soft);
            color: var(--accent);
            border: 1px solid #bedff1;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            margin-top: 0.25rem;
        }
        .stat-card {
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--surface);
            padding: 0.85rem 0.95rem;
            min-height: 96px;
            box-shadow: 0 1px 2px rgba(15, 35, 52, 0.05);
        }
        .stat-card .label {
            color: var(--text-muted);
            font-size: 0.78rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            font-weight: 700;
        }
        .stat-card .value {
            color: var(--text);
            font-size: 1.68rem;
            font-weight: 800;
            margin-top: 0.25rem;
            line-height: 1.1;
        }
        .stat-card .note {
            color: var(--text-muted);
            font-size: 0.78rem;
            margin-top: 0.35rem;
        }
        .stat-card.good { background: linear-gradient(180deg, var(--surface) 0%, var(--good-soft) 100%); }
        .stat-card.warn { background: linear-gradient(180deg, var(--surface) 0%, var(--warn-soft) 100%); }
        .stat-card.risk { background: linear-gradient(180deg, var(--surface) 0%, var(--risk-soft) 100%); }
        .section-title {
            font-family: "Avenir Next", "Gill Sans", "Segoe UI", sans-serif;
            color: #173b53;
            font-size: 1.03rem;
            font-weight: 760;
            margin-bottom: 0.1rem;
        }
        .section-subtitle {
            color: var(--text-muted);
            font-size: 0.86rem;
            margin-bottom: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _db_candidates(database_url: str | None, test_database_url: str | None) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    ordered = [
        ("DATABASE_URL", database_url),
        ("TEST_DATABASE_URL", test_database_url),
    ]
    for label, raw in ordered:
        if not raw:
            continue
        cleaned = raw.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append((label, cleaned))

    return candidates


@st.cache_data(show_spinner=False)
def _fetch_summary(database_url: str, refresh_nonce: int) -> pd.DataFrame:
    del refresh_nonce
    production_df, shipping_df, inspection_df = load_sources_from_database(database_url)
    result = reconcile(production_df, shipping_df, inspection_df)
    return result.summary.copy()


def _normalize_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary.copy()

    normalized = summary.copy()
    defaults = {
        "ship_date": pd.NaT,
        "total_defects": 0,
        "customer": "Unknown",
        "top_defect_code": "UNSPECIFIED",
        "production_line": "Unassigned",
        "ship_status": "unknown",
        "reconciliation_status": "insufficient_data",
    }
    for column_name, default_value in defaults.items():
        if column_name not in normalized.columns:
            normalized[column_name] = default_value

    normalized["record_date"] = pd.to_datetime(normalized["record_date"], errors="coerce")
    normalized["ship_date"] = pd.to_datetime(normalized["ship_date"], errors="coerce")
    normalized["total_defects"] = (
        pd.to_numeric(normalized["total_defects"], errors="coerce").fillna(0).astype(int)
    )
    normalized["production_line"] = normalized["production_line"].fillna("Unassigned")
    normalized["top_defect_code"] = normalized["top_defect_code"].fillna("UNSPECIFIED")
    normalized["customer"] = normalized["customer"].fillna("Unknown")
    normalized["ship_status"] = normalized["ship_status"].fillna("unknown")
    normalized["reconciliation_status"] = normalized["reconciliation_status"].fillna(
        "insufficient_data"
    )
    normalized["lot_code"] = normalized["lot_code"].astype(str)

    return normalized.dropna(subset=["record_date"]).reset_index(drop=True)


def _load_summary_fallback(candidates: list[tuple[str, str]], refresh_nonce: int) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for label, url in candidates:
        try:
            return _normalize_summary(_fetch_summary(url, refresh_nonce)), label
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.exception("Database load failed (source=%s)", label)

    if last_error:
        raise RuntimeError("all configured database sources failed") from last_error
    raise RuntimeError("no configured database sources")


def _severity(total_defects: int, ship_status: str) -> str:
    status = ship_status.strip().lower() if ship_status else "unknown"
    if status in {"on_hold", "backordered"}:
        return "Critical"
    if total_defects >= 10:
        return "High"
    if total_defects >= 4:
        return "Medium"
    return "Low"


def _reconciliation_label(status: str) -> str:
    normalized = status.strip().lower() if status else "insufficient_data"
    labels = {
        "reconciled": "Reconciled",
        "missing_sources": "Missing Sources",
        "insufficient_data": "Insufficient",
    }
    return labels.get(normalized, "Insufficient")


def _with_period(summary: pd.DataFrame, grouping: TimeGrouping) -> pd.DataFrame:
    grouped = summary.copy()
    freq = "D" if grouping == "Daily" else "W-SUN" if grouping == "Weekly" else "M"
    grouped["period_start"] = grouped["record_date"].dt.to_period(freq).dt.start_time
    grouped["period_start"] = grouped["period_start"].dt.date
    return grouped


def _build_line_rankings(period_df: pd.DataFrame) -> pd.DataFrame:
    if period_df.empty:
        return pd.DataFrame(columns=["Rank", "Line", "Total Defects"])

    rankings = (
        period_df.groupby("production_line", as_index=False)["total_defects"]
        .sum()
        .sort_values(["total_defects", "production_line"], ascending=[False, True])
    )
    rankings["Rank"] = rankings["total_defects"].rank(method="dense", ascending=False).astype(
        int
    )
    return rankings.rename(
        columns={"production_line": "Line", "total_defects": "Total Defects"}
    )[["Rank", "Line", "Total Defects"]]


def _build_alerts(period_df: pd.DataFrame) -> pd.DataFrame:
    if period_df.empty:
        return pd.DataFrame(columns=["Lot", "Defect", "Severity", "Ship Date", "Customer"])

    alerts = period_df[
        period_df["ship_status"].isin(["shipped", "partial", "on_hold", "backordered"])
        & (
            (period_df["total_defects"] > 0)
            | period_df["ship_status"].isin(["on_hold", "backordered"])
        )
    ].copy()
    if alerts.empty:
        return pd.DataFrame(columns=["Lot", "Defect", "Severity", "Ship Date", "Customer"])

    alerts["Severity"] = alerts.apply(
        lambda row: _severity(int(row["total_defects"]), str(row["ship_status"])),
        axis=1,
    )
    alerts["severity_order"] = alerts["Severity"].map(
        {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    )
    alerts["Lot"] = alerts["lot_code"]
    alerts["Defect"] = alerts["top_defect_code"]
    alerts["Ship Date"] = alerts["ship_date"].dt.date
    alerts["Customer"] = alerts["customer"]

    return alerts.sort_values(
        ["severity_order", "Ship Date", "Lot"], ascending=[True, False, True]
    )[["Lot", "Defect", "Severity", "Ship Date", "Customer"]]


def _build_trend(grouped_df: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    if grouped_df.empty:
        empty = pd.DataFrame(columns=["Period", "Total Defects", "Direction"])
        return empty, "No Data", "No prior period"

    trend = (
        grouped_df.groupby("period_start", as_index=False)["total_defects"]
        .sum()
        .sort_values("period_start")
    )
    trend["prior_total"] = trend["total_defects"].shift(1)
    trend["delta"] = trend["total_defects"] - trend["prior_total"].fillna(trend["total_defects"])
    trend["Direction"] = trend["delta"].apply(
        lambda delta: "Up" if delta > 0 else "Down" if delta < 0 else "Flat"
    )
    if len(trend) == 1:
        trend.loc[trend.index[0], "Direction"] = "Baseline"

    latest = trend.iloc[-1]
    latest_signal = str(latest["Direction"])
    latest_delta = (
        "No prior period"
        if pd.isna(latest["prior_total"])
        else f"{int(latest['delta']):+d} defects vs prior period"
    )

    trend["Period"] = pd.to_datetime(trend["period_start"])
    table = trend[["Period", "total_defects", "Direction"]].rename(
        columns={"total_defects": "Total Defects"}
    )
    return table, latest_signal, latest_delta


def _render_page_header(title: str, subtitle: str, status_text: str) -> None:
    left, right = st.columns([5, 2], vertical_alignment="top")
    with left:
        st.markdown(f'<h1 class="page-title">{title}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="page-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    with right:
        st.markdown(f'<p class="status-chip">{status_text}</p>', unsafe_allow_html=True)


def _render_stat_card(label: str, value: str, note: str, tone: str = "neutral") -> None:
    tone_class = tone if tone in {"neutral", "good", "warn", "risk"} else "neutral"
    st.markdown(
        f"""
        <div class="stat-card {tone_class}">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def _render_table_card(
    title: str,
    subtitle: str,
    frame: pd.DataFrame,
    *,
    empty_message: str,
    height: int = 360,
) -> None:
    with st.container(border=True):
        _render_section_header(title, subtitle)
        if frame.empty:
            st.info(empty_message)
            return
        st.dataframe(frame, hide_index=True, use_container_width=True, height=height)


def _render_sidebar() -> tuple[str, TimeGrouping, bool]:
    with st.sidebar:
        st.markdown('<p class="shell-title">Ops Signal</p>', unsafe_allow_html=True)
        st.markdown('<p class="shell-subtitle">Operations + Quality Console</p>', unsafe_allow_html=True)

        page = st.radio(
            "View",
            options=["Dashboard", "Lot Lookup"],
            key="shell_page",
        )

        grouping: TimeGrouping = "Weekly"
        if page == "Dashboard":
            grouping = st.segmented_control(
                "Time Grouping",
                options=["Daily", "Weekly", "Monthly"],
                default=st.session_state.get("shell_grouping", "Weekly"),
                selection_mode="single",
                key="shell_grouping",
            )
        else:
            grouping = st.session_state.get("shell_grouping", "Weekly")

        refresh = st.button("Refresh from DB", type="primary", use_container_width=True)

        source = st.session_state.get("loaded_source", "--")
        loaded_at = st.session_state.get("loaded_at", "--")
        st.markdown(
            f'<div class="shell-meta">Source: <b>{source}</b><br/>Last Sync: <b>{loaded_at}</b></div>',
            unsafe_allow_html=True,
        )

    return page, grouping, refresh


def _dashboard_kpis(period_rows: pd.DataFrame, alerts: pd.DataFrame) -> tuple[str, str, str, str]:
    total_rows = len(period_rows)
    total_defects = int(period_rows["total_defects"].sum()) if not period_rows.empty else 0
    critical_high = int(alerts["Severity"].isin(["Critical", "High"]).sum()) if not alerts.empty else 0

    if period_rows.empty:
        reconciled_rate = 0.0
    else:
        reconciled_rate = float((period_rows["reconciliation_status"] == "reconciled").mean())

    return (
        f"{total_rows}",
        f"{total_defects}",
        f"{critical_high}",
        f"{reconciled_rate * 100:.0f}%",
    )


def _render_dashboard_page(
    summary: pd.DataFrame,
    grouping: TimeGrouping,
    loaded_source: str,
    loaded_at: str,
) -> None:
    _render_page_header(
        "Operational Signal Dashboard",
        "At-a-glance operational view with ranked lines, risk alerts, and defect trend direction.",
        f"Auto-loaded from {loaded_source} at {loaded_at}",
    )

    if summary.empty:
        st.info("No operational rows were returned from the database.")
        return

    grouped = _with_period(summary, grouping)
    latest_period = grouped["period_start"].max()
    period_rows = grouped[grouped["period_start"] == latest_period].copy()

    alerts = _build_alerts(period_rows)
    rankings = _build_line_rankings(period_rows)
    trend, latest_signal, latest_delta = _build_trend(grouped)

    total_rows, total_defects, critical_high, reconciled_rate = _dashboard_kpis(period_rows, alerts)

    st.caption(f"Current grouped period start: {latest_period} ({grouping})")

    k1, k2, k3, k4 = st.columns(4, gap="large")
    with k1:
        _render_stat_card("Rows in Scope", total_rows, "Rows in latest grouped period")
    with k2:
        _render_stat_card("Total Defects", total_defects, "Summed from grouped rows", tone="warn")
    with k3:
        _render_stat_card("Critical/High Alerts", critical_high, "Shipping-exposed risk lots", tone="risk")
    with k4:
        _render_stat_card("Reconciled Rate", reconciled_rate, "Rows fully reconciled", tone="good")

    st.markdown("")
    left, right = st.columns([1.05, 1.35], gap="large")

    with left:
        _render_table_card(
            "Production Line Rankings",
            "Ranked by total defects in current grouped period.",
            rankings,
            empty_message="No production ranking rows for this period.",
            height=370,
        )

    with right:
        _render_table_card(
            "Shipping Risk Alerts",
            "Lots prioritized by severity, then ship date.",
            alerts,
            empty_message="No shipping risk alerts for this period.",
            height=370,
        )

    with st.container(border=True):
        _render_section_header(
            "Defect Trend Signals",
            "Trend direction compares each period against its prior period.",
        )
        t_left, t_right = st.columns([1.7, 1], gap="large")
        with t_left:
            if trend.empty:
                st.info("No trend data available.")
            else:
                chart_df = trend.set_index("Period")[["Total Defects"]]
                st.line_chart(chart_df, use_container_width=True, height=260)
        with t_right:
            st.metric("Latest Direction", latest_signal, latest_delta)
            trend_table = trend.copy()
            trend_table["Period"] = trend_table["Period"].dt.date
            st.dataframe(trend_table, hide_index=True, use_container_width=True, height=260)


def _clamp_date(value: date, minimum: date, maximum: date) -> date:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _render_lot_lookup_page(summary: pd.DataFrame, loaded_source: str, loaded_at: str) -> None:
    _render_page_header(
        "Lot Lookup",
        "Query lots quickly by id and date range, then inspect severity and reconciliation state.",
        f"Auto-loaded from {loaded_source} at {loaded_at}",
    )

    if summary.empty:
        st.info("No operational rows were returned from the database.")
        return

    min_date = summary["record_date"].min().date()
    max_date = summary["record_date"].max().date()

    if "lot_lookup_filters" not in st.session_state:
        st.session_state["lot_lookup_filters"] = {
            "lot_query": "",
            "start_date": min_date,
            "end_date": max_date,
        }

    filters = st.session_state["lot_lookup_filters"]
    filters["start_date"] = _clamp_date(filters["start_date"], min_date, max_date)
    filters["end_date"] = _clamp_date(filters["end_date"], min_date, max_date)

    with st.container(border=True):
        _render_section_header(
            "Filter Panel",
            "Use filters to narrow results, then run search.",
        )
        with st.form("lot_lookup_form"):
            f1, f2, f3 = st.columns([2.2, 1, 1], gap="large")
            lot_query = f1.text_input("Lot ID", value=filters["lot_query"], placeholder="e.g. 20260112001")
            start_date = f2.date_input(
                "Start Date",
                value=filters["start_date"],
                min_value=min_date,
                max_value=max_date,
            )
            end_date = f3.date_input(
                "End Date",
                value=filters["end_date"],
                min_value=min_date,
                max_value=max_date,
            )

            a1, a2, _ = st.columns([1, 1, 3])
            search_clicked = a1.form_submit_button("Search", type="primary", use_container_width=True)
            clear_clicked = a2.form_submit_button("Clear", use_container_width=True)

    if clear_clicked:
        st.session_state["lot_lookup_filters"] = {
            "lot_query": "",
            "start_date": min_date,
            "end_date": max_date,
        }
        st.rerun()

    if search_clicked:
        st.session_state["lot_lookup_filters"] = {
            "lot_query": lot_query.strip(),
            "start_date": start_date,
            "end_date": end_date,
        }

    active = st.session_state["lot_lookup_filters"]
    if active["start_date"] > active["end_date"]:
        st.error("Start date must be on or before end date.")
        return

    filtered = summary[
        (summary["record_date"].dt.date >= active["start_date"])
        & (summary["record_date"].dt.date <= active["end_date"])
    ].copy()

    if active["lot_query"]:
        filtered = filtered[
            filtered["lot_code"].str.contains(active["lot_query"], case=False, na=False)
        ]

    filtered["Severity"] = filtered.apply(
        lambda row: _severity(int(row["total_defects"]), str(row["ship_status"])),
        axis=1,
    )
    filtered["Reconciliation"] = filtered["reconciliation_status"].map(_reconciliation_label)

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    filtered["severity_order"] = filtered["Severity"].map(severity_order).fillna(4)

    filtered = filtered.sort_values(
        ["record_date", "severity_order", "lot_code"],
        ascending=[False, True, True],
    )

    lookup_rows = len(filtered)
    lookup_critical = int(filtered["Severity"].isin(["Critical", "High"]).sum()) if lookup_rows else 0
    lookup_reconciled = (
        float((filtered["reconciliation_status"] == "reconciled").mean()) if lookup_rows else 0.0
    )

    s1, s2, s3 = st.columns(3, gap="large")
    with s1:
        _render_stat_card("Matches", f"{lookup_rows}", "Rows matching active filters")
    with s2:
        _render_stat_card("Critical/High", f"{lookup_critical}", "High-priority matched rows", tone="risk")
    with s3:
        _render_stat_card("Reconciled Rate", f"{lookup_reconciled * 100:.0f}%", "Within matched rows", tone="good")

    display = filtered.rename(
        columns={
            "lot_code": "Lot ID",
            "record_date": "Record Date",
            "production_line": "Production Line",
            "total_defects": "Total Defects",
            "top_defect_code": "Top Defect",
            "ship_status": "Ship Status",
            "ship_date": "Ship Date",
            "customer": "Customer",
        }
    )
    display["Record Date"] = pd.to_datetime(display["Record Date"]).dt.date
    display["Ship Date"] = pd.to_datetime(display["Ship Date"], errors="coerce").dt.date

    _render_table_card(
        "Lookup Results",
        "Rows sorted by record date and severity for quick scanning.",
        display[
            [
                "Lot ID",
                "Record Date",
                "Production Line",
                "Total Defects",
                "Top Defect",
                "Severity",
                "Ship Status",
                "Reconciliation",
                "Ship Date",
                "Customer",
            ]
        ],
        empty_message="No rows matched the active filters.",
        height=430,
    )


def main() -> None:
    _configure_logging()
    _init_sentry()
    _inject_theme()

    if "refresh_nonce" not in st.session_state:
        st.session_state["refresh_nonce"] = 0

    page, grouping, refresh_clicked = _render_sidebar()
    if refresh_clicked:
        st.session_state["refresh_nonce"] += 1
        st.rerun()

    settings = get_settings(test=True)
    candidates = _db_candidates(settings.database_url, settings.test_database_url)
    if not candidates:
        st.error("No configured database source was found.")
        st.stop()

    try:
        with st.spinner("Auto-loading from database..."):
            summary, loaded_source = _load_summary_fallback(
                candidates,
                st.session_state["refresh_nonce"],
            )
    except Exception:  # noqa: BLE001
        st.error("Database load failed. Verify DB connectivity and credentials.")
        st.stop()

    loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["loaded_source"] = loaded_source
    st.session_state["loaded_at"] = loaded_at

    if page == "Dashboard":
        _render_dashboard_page(summary, grouping, loaded_source, loaded_at)
    else:
        _render_lot_lookup_page(summary, loaded_source, loaded_at)


if __name__ == "__main__":
    main()
