"""Compare one file's source rows with what Postgres stored for it."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from .validate import Reject, ValidOrder


@dataclass(frozen=True)
class Reconciliation:
    source_rows: int
    loaded_count: int
    rejected_count: int
    accepted_amount: Decimal
    loaded_amount: Decimal
    order_ids: tuple[str, ...]

    @property
    def ok(self) -> bool:
        counts = self.source_rows == self.loaded_count + self.rejected_count
        amounts = self.accepted_amount == self.loaded_amount
        return counts and amounts and not self.order_ids


def reconcile_file(
    conn: Connection,
    source_file: str,
    source_rows: int,
    valid_orders: list[ValidOrder],
    rejects: list[Reject],
) -> Reconciliation:
    """Source rows come from the file. Loaded and rejected rows come from Postgres."""
    stored = conn.execute(
        "SELECT order_id, amount FROM orders WHERE source_file = %s",
        (source_file,),
    ).fetchall()
    stored_rejects = conn.execute(
        "SELECT order_id FROM order_rejects WHERE source_file = %s",
        (source_file,),
    ).fetchall()

    loaded = {order_id: amount for order_id, amount in stored}
    accepted = {order.order_id: order.amount for order in valid_orders}
    accepted_amount = sum(accepted.values(), Decimal("0"))
    loaded_amount = sum(loaded.values(), Decimal("0"))

    order_ids = _differing_ids(accepted, loaded, rejects, stored_rejects)
    return Reconciliation(
        source_rows=source_rows,
        loaded_count=len(loaded),
        rejected_count=len(stored_rejects),
        accepted_amount=accepted_amount,
        loaded_amount=loaded_amount,
        order_ids=order_ids,
    )


def _differing_ids(accepted, loaded, rejects, stored_rejects) -> tuple[str, ...]:
    ids = set(accepted) ^ set(loaded)
    ids.update(
        order_id
        for order_id in set(accepted) & set(loaded)
        if accepted[order_id] != loaded[order_id]
    )
    file_rejects = Counter(reject.order_id for reject in rejects if reject.order_id)
    db_rejects = Counter(order_id for (order_id,) in stored_rejects if order_id)
    ids.update((file_rejects - db_rejects).elements())
    ids.update((db_rejects - file_rejects).elements())
    return tuple(sorted(ids))
