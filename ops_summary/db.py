"""Database IO helpers for pulling source records into reconciliation pipelines."""

from __future__ import annotations

from collections.abc import Iterable
import logging

import pandas as pd
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _normalize_database_url(database_url: str) -> str:
    """Normalize DSNs so SQLAlchemy uses installed drivers."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def make_engine(database_url: str) -> Engine:
    """Create an SQLAlchemy engine for the configured database URL."""
    normalized_url = _normalize_database_url(database_url)
    scheme = normalized_url.partition(":")[0] or "unknown"
    logger.debug("Creating SQLAlchemy engine (scheme=%s)", scheme)
    return create_engine(normalized_url, pool_pre_ping=True)


def _ops_table(engine: Engine, table_name: str) -> str:
    if engine.dialect.name == "sqlite":
        return f"ops_{table_name}"
    return f"ops.{table_name}"


def _read_sql(engine: Engine, sql_text: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql_text), conn)


def _safe_read(engine: Engine, sql_candidates: Iterable[str]) -> pd.DataFrame:
    for candidate_number, query in enumerate(sql_candidates, start=1):
        try:
            frame = _read_sql(engine, query)
            logger.debug(
                "SQL query candidate succeeded (candidate=%s, rows=%s)",
                candidate_number,
                len(frame),
            )
            return frame
        except SQLAlchemyError as exc:
            logger.warning(
                "SQL query candidate failed (candidate=%s, error=%s)",
                candidate_number,
                exc.__class__.__name__,
            )
            continue
    logger.warning("All SQL query candidates failed; returning empty DataFrame")
    return pd.DataFrame()


def load_sources_from_database(
    database_url: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load production/shipping/inspection records from PostgreSQL or sqlite test DB."""
    logger.info("Loading reconciliation source data from database")
    engine = make_engine(database_url)

    lots = _ops_table(engine, "lots")
    production = _ops_table(engine, "production_records")
    shipping = _ops_table(engine, "shipping_records")
    inspection = _ops_table(engine, "inspection_records")
    defects = _ops_table(engine, "defect_observations")
    defect_types = _ops_table(engine, "defect_types")

    production_query = f"""
        SELECT
            l.lot_code AS "Lot ID",
            p.production_date AS "Date",
            p.shift AS "Shift",
            p.production_line AS "Production Line",
            p.part_number AS "Part Number",
            p.units_planned AS "Units Planned",
            p.units_actual AS "Units Actual",
            p.downtime_minutes AS "Downtime (min)",
            p.line_issue_flag AS "Line Issue?",
            p.primary_issue AS "Primary Issue",
            p.supervisor_notes AS "Supervisor Notes"
        FROM {production} p
        JOIN {lots} l ON l.lot_id = p.lot_id
    """

    shipping_query = f"""
        SELECT
            l.lot_code AS "Lot ID",
            s.ship_date AS "Ship Date",
            s.sales_order_number AS "Sales Order #",
            s.customer AS "Customer",
            s.destination_state AS "Destination (State)",
            s.carrier AS "Carrier",
            s.bol_number AS "BOL #",
            s.tracking_pro AS "Tracking / PRO",
            s.qty_shipped AS "Qty Shipped",
            s.ship_status AS "Ship Status",
            s.hold_reason AS "Hold Reason",
            s.shipping_notes AS "Shipping Notes"
        FROM {shipping} s
        JOIN {lots} l ON l.lot_id = s.lot_id
    """

    inspection_query = f"""
        SELECT
            l.lot_code AS "Lot ID",
            i.inspection_date AS "Inspection Date",
            dt.defect_code AS "Defect Type",
            d.qty_defects AS "Defect Qty",
            i.overall_result AS "Overall Result"
        FROM {inspection} i
        JOIN {lots} l ON l.lot_id = i.lot_id
        LEFT JOIN {defects} d ON d.inspection_record_id = i.inspection_record_id
        LEFT JOIN {defect_types} dt ON dt.defect_type_id = d.defect_type_id
    """

    production_df = _safe_read(engine, [production_query])
    shipping_df = _safe_read(engine, [shipping_query])
    inspection_df = _safe_read(engine, [inspection_query])

    logger.info(
        "Loaded source data rows: production=%s shipping=%s inspection=%s",
        len(production_df),
        len(shipping_df),
        len(inspection_df),
    )

    return production_df, shipping_df, inspection_df
