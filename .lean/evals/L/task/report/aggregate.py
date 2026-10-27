"""Totals by category."""


def totals(rows):
    result = {}
    for category, amount in rows:
        result[category] = result.get(category, 0) + amount
    return result
