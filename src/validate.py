"""The validation rules. Pure Python: no S3, no database, so it is cheap to test."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .parsers import RawRow

REQUIRED_FIELDS = ("order_id", "customer_id", "order_date", "amount", "currency")
DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class ValidOrder:
    order_id: str
    customer_id: str
    order_date: date
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class Reject:
    row_number: int
    order_id: str | None  # may be missing or blank, so it is nullable
    reason: str
    raw_row: dict[str, str]


def validate_rows(rows: list[RawRow]) -> tuple[list[ValidOrder], list[Reject]]:
    """Return (valid, rejects). Every input row appears in exactly one of the two."""
    valid: list[ValidOrder] = []
    rejects: list[Reject] = []
    # Only ids that actually passed. A rejected row never claims its id.
    seen_order_ids: set[str] = set()

    for row in rows:
        outcome = _validate_one(row, seen_order_ids)
        if isinstance(outcome, Reject):
            rejects.append(outcome)
            continue
        seen_order_ids.add(outcome.order_id)
        valid.append(outcome)

    # Nothing may vanish: each source row is either loaded or rejected.
    assert len(rows) == len(valid) + len(rejects)
    return valid, rejects


def _validate_one(row: RawRow, seen_order_ids: set[str]) -> ValidOrder | Reject:
    """First failing rule wins. Later rules are not checked."""
    values = row.values

    for name in REQUIRED_FIELDS:
        if not values.get(name, "").strip():
            return _reject(row, f"missing_required_field:{name}")

    try:
        amount = Decimal(values["amount"])
    except InvalidOperation:
        return _reject(row, "invalid_amount")
    # Decimal("NaN") and Decimal("Infinity") do not raise.
    if not amount.is_finite():
        return _reject(row, "invalid_amount")
    if amount < 0:
        return _reject(row, "negative_amount")

    try:
        order_date = datetime.strptime(values["order_date"], DATE_FORMAT).date()
    except ValueError:
        return _reject(row, "invalid_date")

    if values["order_id"] in seen_order_ids:
        return _reject(row, "duplicate_order_id")

    return ValidOrder(
        order_id=values["order_id"],
        customer_id=values["customer_id"],
        order_date=order_date,
        amount=amount,
        currency=values["currency"],
    )


def _reject(row: RawRow, reason: str) -> Reject:
    order_id = row.values.get("order_id", "").strip() or None
    return Reject(
        row_number=row.row_number,
        order_id=order_id,
        reason=reason,
        raw_row=dict(row.values),
    )
