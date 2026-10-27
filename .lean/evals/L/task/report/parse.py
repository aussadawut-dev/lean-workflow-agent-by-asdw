"""Read expense rows."""
import csv


def parse_amount(text):
    return float(text.strip())


def read_rows(path):
    with open(path, newline="") as handle:
        return [(row["category"], parse_amount(row["amount"])) for row in csv.DictReader(handle)]
