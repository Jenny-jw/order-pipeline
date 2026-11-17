-- Reconciliation: where did each source file's rows end up?
--
-- The database only knows what was stored. It does not remember how many rows
-- the file originally had, so "source rows = loaded + rejected" is checked in
-- Python against the file. This query is the database half of that check.
--
-- Run:
--   docker compose exec -T postgres psql -U orders_app -d orders < sql/reconcile.sql

-- One row per file: how many orders were loaded, their amount, how many were rejected.
WITH loaded AS (
    SELECT source_file,
           count(*)    AS loaded_count,
           sum(amount) AS loaded_amount
    FROM orders
    GROUP BY source_file
),
rejected AS (
    SELECT source_file,
           count(*) AS rejected_count
    FROM order_rejects
    GROUP BY source_file
)
SELECT COALESCE(loaded.source_file, rejected.source_file) AS source_file,
       COALESCE(loaded.loaded_count, 0)                   AS loaded_count,
       COALESCE(loaded.loaded_amount, 0)                  AS loaded_amount,
       COALESCE(rejected.rejected_count, 0)               AS rejected_count,
       COALESCE(loaded.loaded_count, 0)
           + COALESCE(rejected.rejected_count, 0)         AS accounted_rows
FROM loaded
FULL OUTER JOIN rejected USING (source_file)
ORDER BY source_file;

-- One row per order, so a mismatch can be traced to an order_id and a reason.
SELECT source_file,
       order_id,
       'loaded' AS outcome,
       amount,
       NULL     AS reason,
       NULL     AS row_number
FROM orders
UNION ALL
SELECT source_file,
       order_id,
       'rejected',
       NULL,
       reason,
       row_number
FROM order_rejects
ORDER BY source_file, row_number NULLS FIRST, order_id;
