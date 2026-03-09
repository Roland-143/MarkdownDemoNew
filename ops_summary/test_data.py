"""Utilities for initializing a deterministic test database."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    if not url.database or url.database == ":memory:":
        return

    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def initialize_test_database(database_url: str) -> None:
    """Create and seed minimal DB tables used in integration and e2e tests."""
    _ensure_sqlite_parent(database_url)
    engine = create_engine(database_url)

    with engine.begin() as conn:
        # Drop old tables for deterministic test runs.
        conn.execute(text("DROP TABLE IF EXISTS ops_defect_observations"))
        conn.execute(text("DROP TABLE IF EXISTS ops_defect_types"))
        conn.execute(text("DROP TABLE IF EXISTS ops_inspection_records"))
        conn.execute(text("DROP TABLE IF EXISTS ops_shipping_records"))
        conn.execute(text("DROP TABLE IF EXISTS ops_production_records"))
        conn.execute(text("DROP TABLE IF EXISTS ops_lots"))

        conn.execute(
            text(
                """
                CREATE TABLE ops_lots (
                    lot_id INTEGER PRIMARY KEY,
                    lot_code TEXT NOT NULL UNIQUE
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE ops_production_records (
                    production_record_id INTEGER PRIMARY KEY,
                    lot_id INTEGER NOT NULL,
                    production_date TEXT,
                    shift TEXT,
                    production_line TEXT,
                    part_number TEXT,
                    units_planned INTEGER,
                    units_actual INTEGER,
                    downtime_minutes INTEGER,
                    line_issue_flag INTEGER,
                    primary_issue TEXT,
                    supervisor_notes TEXT,
                    FOREIGN KEY(lot_id) REFERENCES ops_lots(lot_id)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE ops_shipping_records (
                    shipping_record_id INTEGER PRIMARY KEY,
                    lot_id INTEGER NOT NULL,
                    ship_date TEXT,
                    sales_order_number TEXT,
                    customer TEXT,
                    destination_state TEXT,
                    carrier TEXT,
                    bol_number TEXT,
                    tracking_pro TEXT,
                    qty_shipped INTEGER,
                    ship_status TEXT,
                    hold_reason TEXT,
                    shipping_notes TEXT,
                    FOREIGN KEY(lot_id) REFERENCES ops_lots(lot_id)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE ops_inspection_records (
                    inspection_record_id INTEGER PRIMARY KEY,
                    lot_id INTEGER NOT NULL,
                    inspection_date TEXT,
                    inspection_stage TEXT,
                    inspector TEXT,
                    overall_result TEXT,
                    FOREIGN KEY(lot_id) REFERENCES ops_lots(lot_id)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE ops_defect_types (
                    defect_type_id INTEGER PRIMARY KEY,
                    defect_code TEXT NOT NULL UNIQUE
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE ops_defect_observations (
                    defect_observation_id INTEGER PRIMARY KEY,
                    inspection_record_id INTEGER NOT NULL,
                    defect_type_id INTEGER NOT NULL,
                    qty_defects INTEGER NOT NULL,
                    FOREIGN KEY(inspection_record_id) REFERENCES ops_inspection_records(inspection_record_id),
                    FOREIGN KEY(defect_type_id) REFERENCES ops_defect_types(defect_type_id)
                )
                """
            )
        )

        conn.execute(
            text("INSERT INTO ops_lots (lot_id, lot_code) VALUES (1, '20260112001')")
        )

        conn.execute(
            text(
                """
                INSERT INTO ops_production_records (
                    production_record_id,
                    lot_id,
                    production_date,
                    shift,
                    production_line,
                    part_number,
                    units_planned,
                    units_actual,
                    downtime_minutes,
                    line_issue_flag,
                    primary_issue,
                    supervisor_notes
                ) VALUES (
                    1,
                    1,
                    '2026-01-12',
                    'Day',
                    'Line 1',
                    'SW-8091-A',
                    400,
                    382,
                    44,
                    1,
                    'Sensor fault',
                    'Sensor replaced'
                )
                """
            )
        )

        conn.execute(
            text(
                """
                INSERT INTO ops_shipping_records (
                    shipping_record_id,
                    lot_id,
                    ship_date,
                    sales_order_number,
                    customer,
                    destination_state,
                    carrier,
                    bol_number,
                    tracking_pro,
                    qty_shipped,
                    ship_status,
                    hold_reason,
                    shipping_notes
                ) VALUES (
                    1,
                    1,
                    '2026-01-12',
                    'SO-1001',
                    'Campus Ops',
                    'IN',
                    'FedEx',
                    'BOL-1001',
                    'TRK-1001',
                    380,
                    'shipped',
                    NULL,
                    'Loaded to dock 2'
                )
                """
            )
        )

        conn.execute(
            text(
                """
                INSERT INTO ops_inspection_records (
                    inspection_record_id,
                    lot_id,
                    inspection_date,
                    inspection_stage,
                    inspector,
                    overall_result
                ) VALUES (
                    1,
                    1,
                    '2026-01-12',
                    'final',
                    'qa-1',
                    'fail'
                )
                """
            )
        )

        conn.execute(
            text(
                "INSERT INTO ops_defect_types (defect_type_id, defect_code) VALUES (1, 'CRACK')"
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO ops_defect_observations (
                    defect_observation_id,
                    inspection_record_id,
                    defect_type_id,
                    qty_defects
                ) VALUES (1, 1, 1, 7)
                """
            )
        )
