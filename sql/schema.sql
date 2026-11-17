-- Loaded orders. One row per order_id, ever.
CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT          NOT NULL,
    order_date  DATE          NOT NULL,
    amount      NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    currency    CHAR(3)       NOT NULL,
    source_file TEXT          NOT NULL,
    loaded_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Rows that failed validation, kept with the original values for investigation.
CREATE TABLE IF NOT EXISTS order_rejects (
    reject_id   BIGSERIAL PRIMARY KEY,
    source_file TEXT        NOT NULL,
    row_number  INTEGER     NOT NULL,
    order_id    TEXT,
    reason      TEXT        NOT NULL,
    raw_row     JSONB       NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per (file, content) pair that has been processed. Drives idempotency.
CREATE TABLE IF NOT EXISTS ingested_files (
    file_id        BIGSERIAL PRIMARY KEY,
    s3_key         TEXT          NOT NULL,
    etag           TEXT          NOT NULL,
    source_rows    INTEGER       NOT NULL,
    loaded_count   INTEGER       NOT NULL,
    rejected_count INTEGER       NOT NULL,
    amount_total   NUMERIC(14,2) NOT NULL,
    processed_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (s3_key, etag)
);

CREATE INDEX IF NOT EXISTS idx_orders_source_file ON orders (source_file);
CREATE INDEX IF NOT EXISTS idx_rejects_source_file ON order_rejects (source_file);
