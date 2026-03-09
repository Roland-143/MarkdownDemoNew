-- db/docker_seed.sql
-- Minimal valid seed data for local docker-compose startup.
BEGIN;

INSERT INTO ops.import_batches (
  source_system,
  source_file,
  source_sheet,
  imported_by
)
VALUES
  ('production', 'docker_seed.sql', 'Production', 'docker-compose'),
  ('shipping', 'docker_seed.sql', 'Shipping', 'docker-compose'),
  ('inspection', 'docker_seed.sql', 'Inspection', 'docker-compose');

INSERT INTO ops.lots (
  lot_code,
  lot_code_example_raw,
  notes
)
VALUES ('20260112001', 'LOT-20260112-001', 'Local docker demo row')
ON CONFLICT (lot_code) DO NOTHING;

INSERT INTO ops.defect_types (
  defect_code,
  defect_name
)
VALUES ('CRACK', 'Surface crack')
ON CONFLICT (defect_code) DO NOTHING;

WITH lot AS (
  SELECT lot_id
  FROM ops.lots
  WHERE lot_code = '20260112001'
),
production_batch AS (
  SELECT import_batch_id
  FROM ops.import_batches
  WHERE source_system = 'production'
  ORDER BY import_batch_id DESC
  LIMIT 1
)
INSERT INTO ops.production_records (
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
  supervisor_notes,
  import_batch_id,
  source_row_id,
  lot_id_raw
)
SELECT
  lot.lot_id,
  DATE '2026-01-12',
  'Day',
  'Line 1',
  'SW-8091-A',
  400,
  382,
  44,
  TRUE,
  'Sensor fault',
  'Sensor replaced',
  production_batch.import_batch_id,
  1,
  'LOT-20260112-001'
FROM lot
CROSS JOIN production_batch;

WITH lot AS (
  SELECT lot_id
  FROM ops.lots
  WHERE lot_code = '20260112001'
),
shipping_batch AS (
  SELECT import_batch_id
  FROM ops.import_batches
  WHERE source_system = 'shipping'
  ORDER BY import_batch_id DESC
  LIMIT 1
)
INSERT INTO ops.shipping_records (
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
  shipping_notes,
  import_batch_id,
  source_row_id,
  lot_id_raw
)
SELECT
  lot.lot_id,
  DATE '2026-01-12',
  'SO-1001',
  'Campus Ops',
  'IN',
  'FedEx',
  'BOL-1001',
  'TRK-1001',
  380,
  'shipped',
  NULL,
  'Loaded to dock 2',
  shipping_batch.import_batch_id,
  1,
  'LOT-20260112-001'
FROM lot
CROSS JOIN shipping_batch;

WITH lot AS (
  SELECT lot_id
  FROM ops.lots
  WHERE lot_code = '20260112001'
),
inspection_batch AS (
  SELECT import_batch_id
  FROM ops.import_batches
  WHERE source_system = 'inspection'
  ORDER BY import_batch_id DESC
  LIMIT 1
),
inserted_inspection AS (
  INSERT INTO ops.inspection_records (
    lot_id,
    inspection_date,
    inspection_stage,
    inspector,
    overall_result,
    import_batch_id,
    source_row_id,
    lot_id_raw
  )
  SELECT
    lot.lot_id,
    DATE '2026-01-12',
    'final',
    'qa-1',
    'fail',
    inspection_batch.import_batch_id,
    1,
    'INS-20260112001'
  FROM lot
  CROSS JOIN inspection_batch
  RETURNING inspection_record_id
)
INSERT INTO ops.defect_observations (
  inspection_record_id,
  defect_type_id,
  qty_defects,
  notes
)
SELECT
  inserted_inspection.inspection_record_id,
  defect_types.defect_type_id,
  7,
  'docker seed'
FROM inserted_inspection
JOIN ops.defect_types AS defect_types
  ON defect_types.defect_code = 'CRACK';

COMMIT;
