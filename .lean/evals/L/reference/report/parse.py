"""Read expense rows."""
import csv
from decimal import Decimal, InvalidOperation


def parse_amount(text):
    value = text.strip()
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1].strip()
    value = value.replace(",", "")
    if not value:
        raise ValueError("blank amount")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"bad amount: {text!r}") from None
    return -amount if negative else amount


def read_rows(path):
    with open(path, newline="") as handle:
        return [(row["category"], parse_amount(row["amount"])) for row in csv.DictReader(handle)]
