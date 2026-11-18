"""Read order files from S3, validate them, and load them into Postgres.

Run with: python -m src.pipeline
"""

import sys
from dataclasses import dataclass

import psycopg

from .config import Config, load_config
from .load import find_processed_at, load_file, record_ingested_file
from .parsers import ParseError, parse
from .reconcile import Reconciliation, reconcile_file
from .s3_client import S3Object, S3Reader
from .validate import validate_rows


@dataclass(frozen=True)
class FileSummary:
    key: str
    read: int
    accepted: int  # rows that passed validation
    inserted: int  # rows newly written; 0 on a rerun
    rejected: int
    error: str | None = None
    mismatch: str | None = None
    skipped: str | None = None


def run(config: Config | None = None) -> list[FileSummary]:
    config = config or load_config()
    reader = S3Reader(config.s3_bucket, config.aws_profile, config.aws_region)
    summaries: list[FileSummary] = []
    with psycopg.connect(config.database_url) as conn:
        for obj in reader.list_data_files(config.s3_prefix):
            summaries.append(_process_file(conn, reader, obj))
    return summaries


def _process_file(conn: psycopg.Connection, reader: S3Reader, obj: S3Object) -> FileSummary:
    # Same key and same ETag means the bytes have not changed since the last load.
    processed_at = find_processed_at(conn, obj.key, obj.etag)
    if processed_at is not None:
        return FileSummary(
            obj.key,
            read=0,
            accepted=0,
            inserted=0,
            rejected=0,
            skipped=f"etag {obj.etag} already processed at {processed_at.isoformat()}",
        )

    text = reader.read_text(obj.key)
    try:
        rows = parse(obj.key, text)
    except ParseError as exc:
        # The file itself is unusable. Skip it and keep going with the next one.
        return FileSummary(obj.key, read=0, accepted=0, inserted=0, rejected=0, error=str(exc))

    valid, rejects = validate_rows(rows)
    result = load_file(conn, obj.key, valid, rejects)
    reconciliation = reconcile_file(conn, obj.key, len(rows), valid, rejects)
    if reconciliation.ok:
        record_ingested_file(
            conn,
            obj.key,
            obj.etag,
            reconciliation.source_rows,
            reconciliation.loaded_count,
            reconciliation.rejected_count,
            reconciliation.accepted_amount,
        )
    return FileSummary(
        key=obj.key,
        read=len(rows),
        accepted=len(valid),
        inserted=result.inserted,
        rejected=result.rejected,
        mismatch=None if reconciliation.ok else _mismatch_line(reconciliation),
    )


def _mismatch_line(result: Reconciliation) -> str:
    parts = []
    accounted = result.loaded_count + result.rejected_count
    if result.source_rows != accounted:
        parts.append(f"rows {result.source_rows} != loaded {result.loaded_count} + rejected {result.rejected_count}")
    if result.accepted_amount != result.loaded_amount:
        parts.append(f"amount {result.accepted_amount} != loaded {result.loaded_amount}")
    ids = ", ".join(result.order_ids) if result.order_ids else "(no order_id)"
    parts.append(f"order_ids: {ids}")
    return "; ".join(parts)


def main() -> None:
    summaries = run()
    print(f"{'file':<32} {'read':>6} {'accepted':>9} {'inserted':>9} {'rejected':>9}")
    for summary in summaries:
        if summary.skipped:
            print(f"{summary.key:<32} skip")
            print(f"  {summary.skipped}")
            continue
        if summary.error:
            print(f"{summary.key:<32} ERROR  {summary.error}")
            continue
        print(
            f"{summary.key:<32} {summary.read:6} {summary.accepted:9} "
            f"{summary.inserted:9} {summary.rejected:9}"
        )
        if summary.mismatch:
            print(f"  mismatch  {summary.mismatch}")
    ran = [summary for summary in summaries if not summary.skipped]
    if ran:
        print(
            f"{'TOTAL':<32} {sum(s.read for s in ran):6} "
            f"{sum(s.accepted for s in ran):9} "
            f"{sum(s.inserted for s in ran):9} "
            f"{sum(s.rejected for s in ran):9}"
        )
    else:
        print(f"{'TOTAL':<32} unchanged; every file was already processed")
    if any(summary.mismatch for summary in summaries):
        sys.exit(1)


if __name__ == "__main__":
    main()
