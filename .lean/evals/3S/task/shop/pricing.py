"""Unit prices and discounts."""

BULK_RATE = 0.10


def bulk_discount(quantity, unit_price):
    """Discount for one cart line: 10% of the line price when quantity is at least 10, else 0."""
    if quantity > 10:
        return round(quantity * unit_price * BULK_RATE, 2)
    return 0.0


def line_total(quantity, unit_price):
    return round(quantity * unit_price - bulk_discount(quantity, unit_price), 2)
