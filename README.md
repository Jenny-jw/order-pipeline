# Order Pipeline

Python pipeline that validates CSV and XML orders from S3, loads them into Postgres, and checks totals with pytest.

A re-runnable order loading flow: files land in S3, Python validates them and writes to a local Postgres, pytest checks row counts and amount totals, and running the same file twice does not create duplicate rows. This is a practice project — it contains no keys and no real data.

## Tech Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ |
| AWS SDK | `boto3` |
| Database | Local Postgres (Docker) |
| DB driver | `psycopg[binary]` (v3) |
| Testing | `pytest` |
| S3 faking | `moto` (optional) |
| Parsing | stdlib `csv`, `xml.etree.ElementTree` |
| Money | `decimal.Decimal`, `NUMERIC(12,2)` |
| Config | Env vars + gitignored `.env` |

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
