"""Totals by category."""
from decimal import Decimal


def totals(rows):
    result = {}
    for category, amount in rows:
        result[category] = result.get(category, Decimal("0")) + Decimal(str(amount))
    return result
