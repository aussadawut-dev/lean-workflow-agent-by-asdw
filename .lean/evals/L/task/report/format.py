"""Text report."""
from .aggregate import totals


def format_report(rows):
    sums = totals(rows)
    lines = [f"{category}: {sums[category]:.2f}" for category in sorted(sums)]
    lines.append(f"TOTAL: {sum(sums.values()):.2f}")
    return "\n".join(lines)
