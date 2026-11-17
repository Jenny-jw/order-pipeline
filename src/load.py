"""Write one file's rows to Postgres. The database keeps the no-duplicate guarantee."""

from dataclasses import dataclass

from psycopg import Connection
from psycopg.types.json import Jsonb

from .validate import Reject, ValidOrder


@dataclass(frozen=True)
class LoadResult:
    inserted: int  # rows newly written to orders
    rejected: int  # rows written to order_rejects


def load_file(
    conn: Connection,
    source_file: str,
    valid_orders: list[ValidOrder],
    rejects: list[Reject],
) -> LoadResult:
    """Load one file in a single transaction.

    A failure anywhere in the block rolls the whole file back, so orders and
    order_rejects never contain half of a file.
    """
    with conn.transaction():
        # Replaces this file's rejects instead of appending, so a rerun does not
        # stack a second copy of the same rejected rows.
        conn.execute(
            "DELETE FROM order_rejects WHERE source_file = %s",
            (source_file,),
        )
        inserted = _insert_orders(conn, source_file, valid_orders)
        _insert_rejects(conn, source_file, rejects)

    return LoadResult(inserted=inserted, rejected=len(rejects))


def _insert_orders(conn: Connection, source_file: str, orders: list[ValidOrder]) -> int:
    inserted = 0
    for order in orders:
        cursor = conn.execute(
            """
            INSERT INTO orders (
                order_id, customer_id, order_date, amount, currency, source_file
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id) DO NOTHING
            """,
            (
                order.order_id,
                order.customer_id,
                order.order_date,
                order.amount,
                order.currency,
                source_file,
            ),
        )
        # 1 when the row was inserted, 0 when order_id was already there.
        inserted += cursor.rowcount
    return inserted


def _insert_rejects(conn: Connection, source_file: str, rejects: list[Reject]) -> None:
    if not rejects:
        return
    conn.cursor().executemany(
        """
        INSERT INTO order_rejects (source_file, row_number, order_id, reason, raw_row)
        VALUES (%s, %s, %s, %s, %s)
        """,
        [
            (source_file, reject.row_number, reject.order_id, reject.reason, Jsonb(reject.raw_row))
            for reject in rejects
        ],
    )
