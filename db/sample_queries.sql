-- db/sample_queries.sql
-- Sample queries for the Unified Operational Summary

-- 1) Weekly summary (filter by date range)
-- Default sorting: shipped+defects first, highest defects, most recent date
SELECT
  os.record_date,
  l.lot_code,
  os.production_line,
  os.units_actual,
  os.total_defects,
  os.top_defect_code,
  os.ship_status,
  os.ship_date,
  os.qty_shipped,
  os.reconciliation_status,
  os.missing_production,
  os.missing_inspection,
  os.missing_shipping,
  os.incomplete_reason
FROM ops.operational_summaries os
JOIN ops.lots l ON l.lot_id = os.lot_id
WHERE os.record_date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'
ORDER BY
  (CASE WHEN os.ship_status IN ('shipped','partial') AND COALESCE(os.total_defects,0) > 0 THEN 1 ELSE 0 END) DESC,
  COALESCE(os.total_defects,0) DESC,
  os.record_date DESC;

-- 2) Priority view: shipped lots with defects (AC7)
SELECT
  os.record_date,
  l.lot_code,
  os.total_defects,
  os.top_defect_code,
  os.ship_status,
  os.ship_date,
  os.qty_shipped
FROM ops.operational_summaries os
JOIN ops.lots l ON l.lot_id = os.lot_id
WHERE os.ship_status IN ('shipped','partial')
  AND COALESCE(os.total_defects,0) > 0
ORDER BY os.record_date DESC, os.total_defects DESC;

-- 3) Filter: by lot + date (AC6) -> the one row the UI would open
SELECT
  os.*,
  l.lot_code
FROM ops.operational_summaries os
JOIN ops.lots l ON l.lot_id = os.lot_id
WHERE l.lot_code = '20260112001'
  AND os.record_date = DATE '2026-01-12';

-- 4) Drill-down (AC9): underlying records for a selected summary row
-- (You can run this after you first get operational_summary_id or lot+date.)
SELECT
  l.lot_code,
  os.record_date,

  -- production
  pr.production_record_id,
  pr.production_date,
  pr.shift,
  pr.production_line,
  pr.part_number,
  pr.units_planned,
  pr.units_actual,
  pr.downtime_minutes,
  pr.line_issue_flag,
  pr.primary_issue,
  pr.supervisor_notes,
  pr.import_batch_id AS production_import_batch_id,
  pr.source_row_id   AS production_source_row_id,

  -- inspection
  ir.inspection_record_id,
  ir.inspection_date,
  ir.inspection_stage,
  ir.inspector,
  ir.overall_result,
  ir.import_batch_id AS inspection_import_batch_id,
  ir.source_row_id   AS inspection_source_row_id,

  -- shipping
  sr.shipping_record_id,
  sr.ship_date,
  sr.sales_order_number,
  sr.customer,
  sr.destination_state,
  sr.carrier,
  sr.bol_number,
  sr.tracking_pro,
  sr.qty_shipped,
  sr.ship_status,
  sr.hold_reason,
  sr.shipping_notes,
  sr.import_batch_id AS shipping_import_batch_id,
  sr.source_row_id   AS shipping_source_row_id

FROM ops.operational_summaries os
JOIN ops.lots l ON l.lot_id = os.lot_id
LEFT JOIN ops.production_records pr ON pr.production_record_id = os.production_record_id
LEFT JOIN ops.inspection_records ir ON ir.inspection_record_id = os.inspection_record_id
LEFT JOIN ops.shipping_records   sr ON sr.shipping_record_id   = os.shipping_record_id
WHERE l.lot_code = '20260112001'
  AND os.record_date = DATE '2026-01-12';

-- 5) Inspection defect breakdown for a lot/date (if inspection data exists)
SELECT
  l.lot_code,
  ir.inspection_date,
  dt.defect_code,
  SUM(do.qty_defects) AS defect_qty
FROM ops.inspection_records ir
JOIN ops.lots l ON l.lot_id = ir.lot_id
JOIN ops.defect_observations do ON do.inspection_record_id = ir.inspection_record_id
JOIN ops.defect_types dt ON dt.defect_type_id = do.defect_type_id
WHERE l.lot_code = '20260112001'
  AND ir.inspection_date = DATE '2026-01-12'
GROUP BY l.lot_code, ir.inspection_date, dt.defect_code
ORDER BY defect_qty DESC;

-- 6) “Incomplete records” count (AC3): rejected rows by reason, by week
SELECT
  DATE_TRUNC('week', r.rejected_at)::DATE AS week_start,
  r.source_system,
  r.reject_reason,
  COUNT(*) AS rejected_count
FROM ops.import_rejects r
GROUP BY 1,2,3
ORDER BY week_start DESC, source_system, rejected_count DESC;

-- 7) Find lots with mismatched dates (AC10-ish):
-- Example: lot has shipping but no matching production date in summaries
SELECT
  l.lot_code,
  sr.ship_date,
  sr.ship_status
FROM ops.shipping_records sr
JOIN ops.lots l ON l.lot_id = sr.lot_id
LEFT JOIN ops.operational_summaries os
  ON os.lot_id = sr.lot_id
 AND os.record_date = sr.ship_date
WHERE os.operational_summary_id IS NULL
ORDER BY sr.ship_date DESC;
