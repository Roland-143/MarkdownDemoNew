-- db/schema.sql
-- PostgreSQL physical data design for Unified Operational Summary (Production + Inspection + Shipping)
-- Conventions:
--   * snake_case for table/column names
--   * plural table names
--   * surrogate PKs everywhere (generated identity)
--   * business keys enforced with UNIQUE
--   * FKs with matching data types + ON DELETE
--   * CHECK constraints for ranges/enums

BEGIN;

-- Optional: keep objects grouped
CREATE SCHEMA IF NOT EXISTS ops;

-- -----------------------------
-- 1) Reference / audit tables
-- -----------------------------

-- Track each import of a spreadsheet (traceability back to file + sheet)
CREATE TABLE IF NOT EXISTS ops.import_batches (
  import_batch_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_system        TEXT NOT NULL,
  source_file          TEXT NOT NULL,
  source_sheet         TEXT NOT NULL,
  imported_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  checksum_sha256      TEXT NULL,
  imported_by          TEXT NULL,
  CONSTRAINT import_batches_source_system_chk
    CHECK (source_system IN ('production','inspection','shipping'))
);

-- Store rows excluded from the main summary due to missing alignment fields or other validation failures (AC3)
CREATE TABLE IF NOT EXISTS ops.import_rejects (
  import_reject_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  import_batch_id      BIGINT NOT NULL REFERENCES ops.import_batches(import_batch_id) ON DELETE CASCADE,
  source_system        TEXT NOT NULL,
  source_row_id        INTEGER NULL,
  reject_reason        TEXT NOT NULL,
  raw_payload          JSONB NULL,
  rejected_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT import_rejects_source_system_chk
    CHECK (source_system IN ('production','inspection','shipping'))
);

CREATE INDEX IF NOT EXISTS import_rejects_batch_idx
  ON ops.import_rejects(import_batch_id);

-- Lots are the join anchor across all sources (canonical business key enforced via UNIQUE)
CREATE TABLE IF NOT EXISTS ops.lots (
  lot_id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lot_code             TEXT NOT NULL, -- canonical normalized lot identifier used for matching (e.g., 20260112001)
  lot_code_example_raw TEXT NULL,     -- optional debugging sample
  notes                TEXT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT lots_lot_code_uk UNIQUE (lot_code)
);

-- -----------------------------
-- 2) Operational source tables
-- -----------------------------

CREATE TABLE IF NOT EXISTS ops.production_records (
  production_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lot_id               BIGINT NOT NULL REFERENCES ops.lots(lot_id) ON DELETE RESTRICT,
  production_date      DATE NULL, -- alignment date (required for inclusion in summary; nullable to allow raw loads)
  shift                TEXT NULL,
  production_line      TEXT NULL,
  part_number          TEXT NULL,
  units_planned        INTEGER NULL,
  units_actual         INTEGER NULL,
  downtime_minutes     INTEGER NULL,
  line_issue_flag      BOOLEAN NULL,
  primary_issue        TEXT NULL,
  supervisor_notes     TEXT NULL,

  -- Traceability
  import_batch_id      BIGINT NOT NULL REFERENCES ops.import_batches(import_batch_id) ON DELETE CASCADE,
  source_row_id        INTEGER NULL,
  lot_id_raw           TEXT NULL,

  CONSTRAINT production_units_planned_chk CHECK (units_planned IS NULL OR units_planned >= 0),
  CONSTRAINT production_units_actual_chk  CHECK (units_actual  IS NULL OR units_actual  >= 0),
  CONSTRAINT production_downtime_chk      CHECK (downtime_minutes IS NULL OR downtime_minutes >= 0)
);

-- Prevent exact duplicate loads of the same spreadsheet row
CREATE UNIQUE INDEX IF NOT EXISTS production_records_import_row_uk
  ON ops.production_records(import_batch_id, source_row_id)
  WHERE source_row_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS production_records_lot_date_idx
  ON ops.production_records(lot_id, production_date);

CREATE INDEX IF NOT EXISTS production_records_line_date_idx
  ON ops.production_records(production_line, production_date);

CREATE TABLE IF NOT EXISTS ops.shipping_records (
  shipping_record_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lot_id               BIGINT NOT NULL REFERENCES ops.lots(lot_id) ON DELETE RESTRICT,
  ship_date            DATE NULL, -- alignment date (nullable to allow raw loads)
  sales_order_number   TEXT NULL,
  customer             TEXT NULL,
  destination_state    CHAR(2) NULL,
  carrier              TEXT NULL,
  bol_number           TEXT NULL,
  tracking_pro         TEXT NULL,
  qty_shipped          INTEGER NULL,
  ship_status          TEXT NULL,
  hold_reason          TEXT NULL,
  shipping_notes       TEXT NULL,

  -- Traceability
  import_batch_id      BIGINT NOT NULL REFERENCES ops.import_batches(import_batch_id) ON DELETE CASCADE,
  source_row_id        INTEGER NULL,
  lot_id_raw           TEXT NULL,

  CONSTRAINT shipping_qty_shipped_chk CHECK (qty_shipped IS NULL OR qty_shipped >= 0),
  CONSTRAINT shipping_state_chk CHECK (destination_state IS NULL OR destination_state ~ '^[A-Z]{2}$'),
  CONSTRAINT shipping_ship_status_chk CHECK (
    ship_status IS NULL OR ship_status IN ('shipped','partial','on_hold','backordered','not_shipped','unknown')
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS shipping_records_import_row_uk
  ON ops.shipping_records(import_batch_id, source_row_id)
  WHERE source_row_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS shipping_records_lot_date_idx
  ON ops.shipping_records(lot_id, ship_date);

CREATE INDEX IF NOT EXISTS shipping_records_status_date_idx
  ON ops.shipping_records(ship_status, ship_date);

-- Inspection sheet not provided yet; table supports future load
CREATE TABLE IF NOT EXISTS ops.inspection_records (
  inspection_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lot_id               BIGINT NOT NULL REFERENCES ops.lots(lot_id) ON DELETE RESTRICT,
  inspection_date      DATE NULL, -- alignment date (nullable to allow raw loads)
  inspection_stage     TEXT NULL,
  inspector            TEXT NULL,
  overall_result       TEXT NULL,

  -- Traceability
  import_batch_id      BIGINT NOT NULL REFERENCES ops.import_batches(import_batch_id) ON DELETE CASCADE,
  source_row_id        INTEGER NULL,
  lot_id_raw           TEXT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS inspection_records_import_row_uk
  ON ops.inspection_records(import_batch_id, source_row_id)
  WHERE source_row_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS inspection_records_lot_date_idx
  ON ops.inspection_records(lot_id, inspection_date);

-- Defect reference + observations (supports multiple defect types per inspection)
CREATE TABLE IF NOT EXISTS ops.defect_types (
  defect_type_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  defect_code          TEXT NOT NULL,
  defect_name          TEXT NULL,
  description          TEXT NULL,
  CONSTRAINT defect_types_defect_code_uk UNIQUE(defect_code)
);

CREATE TABLE IF NOT EXISTS ops.defect_observations (
  defect_observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  inspection_record_id  BIGINT NOT NULL REFERENCES ops.inspection_records(inspection_record_id) ON DELETE CASCADE,
  defect_type_id        BIGINT NOT NULL REFERENCES ops.defect_types(defect_type_id) ON DELETE RESTRICT,
  qty_defects           INTEGER NOT NULL,
  notes                 TEXT NULL,
  CONSTRAINT defect_observations_qty_chk CHECK (qty_defects >= 0),
  CONSTRAINT defect_observations_no_zero_chk CHECK (qty_defects > 0)
);

CREATE INDEX IF NOT EXISTS defect_observations_inspection_idx
  ON ops.defect_observations(inspection_record_id);

CREATE INDEX IF NOT EXISTS defect_observations_defect_type_idx
  ON ops.defect_observations(defect_type_id);

-- -----------------------------
-- 3) Operational summary table
-- -----------------------------
-- Materialized table (your ETL/reconciliation job populates/updates it).
-- Business key: (lot_id, record_date)

CREATE TABLE IF NOT EXISTS ops.operational_summaries (
  operational_summary_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lot_id                 BIGINT NOT NULL REFERENCES ops.lots(lot_id) ON DELETE RESTRICT,
  record_date            DATE NOT NULL, -- primary timeline date for the summary row (typically production_date)

  -- Production (nullable if missing)
  production_record_id   BIGINT NULL REFERENCES ops.production_records(production_record_id) ON DELETE SET NULL,
  production_line        TEXT NULL,
  part_number            TEXT NULL,
  units_planned          INTEGER NULL,
  units_actual           INTEGER NULL,
  downtime_minutes       INTEGER NULL,
  line_issue_flag        BOOLEAN NULL,
  primary_issue          TEXT NULL,

  -- Inspection (nullable if missing)
  inspection_record_id   BIGINT NULL REFERENCES ops.inspection_records(inspection_record_id) ON DELETE SET NULL,
  total_defects          INTEGER NULL,
  top_defect_code        TEXT NULL,

  -- Shipping (nullable if missing)
  shipping_record_id     BIGINT NULL REFERENCES ops.shipping_records(shipping_record_id) ON DELETE SET NULL,
  ship_status            TEXT NOT NULL DEFAULT 'unknown',
  ship_date              DATE NULL,
  qty_shipped            INTEGER NULL,

  -- Completeness / reconciliation flags (AC2/AC4)
  reconciliation_status  TEXT NOT NULL,
  missing_production     BOOLEAN NOT NULL DEFAULT FALSE,
  missing_inspection     BOOLEAN NOT NULL DEFAULT FALSE,
  missing_shipping       BOOLEAN NOT NULL DEFAULT FALSE,
  incomplete_reason      TEXT NULL,

  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT operational_summaries_business_key_uk UNIQUE (lot_id, record_date),
  CONSTRAINT operational_summaries_ship_status_chk CHECK (ship_status IN ('shipped','partial','on_hold','backordered','not_shipped','unknown')),
  CONSTRAINT operational_summaries_recon_status_chk CHECK (reconciliation_status IN ('reconciled','missing_sources','insufficient_data')),
  CONSTRAINT operational_summaries_units_planned_chk CHECK (units_planned IS NULL OR units_planned >= 0),
  CONSTRAINT operational_summaries_units_actual_chk  CHECK (units_actual  IS NULL OR units_actual  >= 0),
  CONSTRAINT operational_summaries_downtime_chk      CHECK (downtime_minutes IS NULL OR downtime_minutes >= 0),
  CONSTRAINT operational_summaries_total_defects_chk CHECK (total_defects IS NULL OR total_defects >= 0),
  CONSTRAINT operational_summaries_qty_shipped_chk   CHECK (qty_shipped IS NULL OR qty_shipped >= 0)
);

-- Support default sorting:
-- (1) shipped lots with defects, (2) highest defect qty, then (3) most recent date
CREATE INDEX IF NOT EXISTS operational_summaries_priority_idx
  ON ops.operational_summaries (
    (CASE WHEN ship_status IN ('shipped','partial') AND COALESCE(total_defects,0) > 0 THEN 1 ELSE 0 END) DESC,
    COALESCE(total_defects,0) DESC,
    record_date DESC
  );

-- Filtering indexes (AC6)
CREATE INDEX IF NOT EXISTS operational_summaries_lot_idx
  ON ops.operational_summaries(lot_id);

CREATE INDEX IF NOT EXISTS operational_summaries_record_date_idx
  ON ops.operational_summaries(record_date);

CREATE INDEX IF NOT EXISTS operational_summaries_ship_status_idx
  ON ops.operational_summaries(ship_status);

CREATE INDEX IF NOT EXISTS operational_summaries_production_line_idx
  ON ops.operational_summaries(production_line);

-- Optional: auto-update updated_at
CREATE OR REPLACE FUNCTION ops.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS operational_summaries_set_updated_at ON ops.operational_summaries;
CREATE TRIGGER operational_summaries_set_updated_at
BEFORE UPDATE ON ops.operational_summaries
FOR EACH ROW EXECUTE FUNCTION ops.set_updated_at();

COMMIT;
