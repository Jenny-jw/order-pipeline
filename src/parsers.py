"""Turn CSV and XML bytes into one common row shape.

Parsers only reshape and rename: every value stays a string so that validation
can report the original text when a value is wrong.
"""

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

FIELDS = ("order_id", "customer_id", "order_date", "amount", "currency")

# The legacy ERP export uses its own element names.
XML_FIELD_MAP = {
    "order_id": "OrderNo",
    "customer_id": "CustomerRef",
    "order_date": "PlacedOn",
    "amount": "TotalAmount",
}

# Only a real ISO timestamp may be shortened to its date part. Anything else is
# passed through untouched so validation reports the value the file really had.
ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T")


@dataclass(frozen=True)
class RawRow:
    # Where to find this row in the source file. CSV: the line number as a text
    # editor shows it, so the header is line 1 and the first order is line 2.
    # XML: the 1-based position of the <Order> element, because XML has no
    # meaningful line numbers once it is reformatted.
    row_number: int
    values: dict[str, str] = field(default_factory=dict)


class ParseError(Exception):
    """The whole file is unusable, so none of its rows can be trusted."""


class UnsupportedFormat(ParseError):
    pass


class SchemaMismatch(ParseError):
    pass


def parse(key: str, text: str) -> list[RawRow]:
    lowered = key.lower()
    if lowered.endswith(".csv"):
        return parse_csv(text)
    if lowered.endswith(".xml"):
        return parse_xml(text)
    raise UnsupportedFormat(f"No parser for {key}")


def parse_csv(text: str) -> list[RawRow]:
    reader = csv.DictReader(io.StringIO(text))
    # Map our field names to the header exactly as written, so a header padded
    # with spaces still lines up. An empty file has no fieldnames at all.
    header = {(name or "").strip(): name for name in (reader.fieldnames or [])}
    missing = [name for name in FIELDS if name not in header]
    if missing:
        raise SchemaMismatch(f"Missing columns: {', '.join(missing)}")

    rows = []
    for raw in reader:
        values = {name: (raw.get(header[name]) or "").strip() for name in FIELDS}
        rows.append(RawRow(row_number=reader.line_num, values=values))
    return rows


def parse_xml(text: str) -> list[RawRow]:
    root = ET.fromstring(text)
    rows = []
    for position, order in enumerate(root.findall("Order"), start=1):
        values = {}
        for name, element in XML_FIELD_MAP.items():
            values[name] = (order.findtext(element) or "").strip()
        # Currency is an attribute of TotalAmount, not an element of its own.
        amount_element = order.find("TotalAmount")
        values["currency"] = (
            amount_element.get("currency", "") if amount_element is not None else ""
        )
        # PlacedOn is a timestamp and the orders table stores a date, but only
        # shorten it when it really is one.
        placed_on = values["order_date"]
        if ISO_TIMESTAMP.match(placed_on):
            values["order_date"] = placed_on[:10]
        rows.append(RawRow(row_number=position, values=values))
    return rows
