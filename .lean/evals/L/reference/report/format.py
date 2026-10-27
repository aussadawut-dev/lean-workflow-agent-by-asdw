"""Text report."""
from decimal import Decimal, ROUND_HALF_UP
from .aggregate import totals


def _money(value):
    return f"{Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def format_report(rows):
    sums = totals(rows)
    lines = [f"{category}: {_money(sums[category])}" for category in sorted(sums)]
    lines.append(f"TOTAL: {_money(sum(sums.values(), Decimal('0')))}")
    return "\n".join(lines)
