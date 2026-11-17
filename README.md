# Order Pipeline

Python pipeline that validates CSV and XML orders from S3, loads them into Postgres, and checks totals with pytest.

A re-runnable order loading flow: files land in S3, Python validates them and writes to a local Postgres, pytest checks row counts and amount totals, and running the same file twice does not create duplicate rows.

## Tech Stack

| Layer     | Choice                                |
| --------- | ------------------------------------- |
| Language  | Python 3.10+                          |
| AWS SDK   | `boto3`                               |
| Database  | Local Postgres (Docker)               |
| DB driver | `psycopg[binary]` (v3)                |
| Testing   | `pytest`                              |
| S3 faking | `moto` (optional)                     |
| Parsing   | stdlib `csv`, `xml.etree.ElementTree` |
| Money     | `decimal.Decimal`, `NUMERIC(12,2)`    |
| Config    | Env vars + gitignored `.env`          |

## Duplicate Order Handling

When the same `order_id` appears more than once, the first occurrence is loaded and every later occurrence is rejected and recorded with the reason `duplicate_order_id`. The rejected row keeps its original values so the discrepancy can be investigated rather than silently discarded.

This matters when the duplicated rows disagree. In `tests/fixtures/orders_bad.csv`, `ORD-2004` appears twice with different amounts:

```
ORD-2004,CUST-504,2026-11-06,1200.00,TWD
ORD-2004,CUST-504,2026-11-06,1350.00,TWD
```

The row with `1200.00` is loaded because it came first; the `1350.00` row is rejected. The pipeline does not try to decide which amount is correct, because nothing in the file says the later row is a correction rather than a duplicate send. Picking first-wins keeps the outcome deterministic — the same file always produces the same table — and leaves the disagreement visible in the rejects table for a human to resolve.

The same rule is enforced twice: in code while validating a file, and by a `UNIQUE` constraint on `orders.order_id` in the database. The constraint guarantees the invariant even if the application logic has a gap.

## Row Numbers

`row_number` on a rejected row means different things per format, because the formats differ in what is useful:

- **CSV**: the line number a text editor shows. The header is line 1, so the first order is line 2.
- **XML**: the 1-based position of the `<Order>` element. XML line numbers are meaningless once a file is reformatted, so the record position is what identifies a row.

## Whole-File Rejection

Some problems belong to the file, not to a row. A CSV whose header is missing a required column cannot produce a single trustworthy row, so the parser raises `SchemaMismatch` and the file is rejected as a whole with one clear reason (`Missing columns: customer_id`) instead of producing one rejected row per line. `UnsupportedFormat` works the same way for an unrecognised extension. Both derive from `ParseError`, so the pipeline has one exception type to catch for file-level failures.

Parsers rename and reshape; they never repair. An XML `PlacedOn` value is shortened to its date part only when it actually matches an ISO timestamp — any other value is passed through untouched so that validation reports, and the rejects table stores, the text the file really contained.

## Project Layout

```
order-pipeline/
├── .gitignore
├── README.md
├── requirements.txt
├── docker-compose.yml       # local Postgres
├── sql/
│   ├── schema.sql           # orders, order_rejects, ingested_files
│   └── reconcile.sql        # reconciliation query
├── src/
│   ├── config.py            # read settings from env
│   ├── s3_client.py         # thin boto3 wrapper
│   ├── parsers.py           # CSV and XML into dicts
│   ├── validate.py          # the three validation rules
│   ├── load.py              # idempotent Postgres writes
│   └── pipeline.py          # entry point
├── tests/
│   ├── conftest.py
│   ├── fixtures/            # local test files
│   └── test_*.py
└── lambda/                  # optional
    └── handler.py
```

Validation (`validate.py`) is kept separate from loading (`load.py`) so validation can be unit-tested in pure Python with no database.
