"""A cart of (quantity, unit price) lines."""
from .pricing import line_total


def cart_total(lines):
    return round(sum(line_total(quantity, price) for quantity, price in lines), 2)
