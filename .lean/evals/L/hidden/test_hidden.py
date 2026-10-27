import sys, unittest
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from report.parse import parse_amount, read_rows
from report.aggregate import totals
from report.format import format_report


class Hidden(unittest.TestCase):
    def test_parse(self):
        for text, expected in (("12.50", "12.50"), ("1,234.50", "1234.50"), ("(12.00)", "-12.00"), ("-3.10", "-3.10"),
                               (" 7 ", "7"), ("(1,000.01)", "-1000.01")):
            with self.subTest(text=text):
                self.assertEqual(Decimal(str(parse_amount(text))), Decimal(expected))
        for bad in ("", "  ", "abc"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_amount(bad)

    def test_exact_totals(self):
        rows = [("a", parse_amount("0.10"))] * 3 + [("b", parse_amount("(0.30)")), ("b", parse_amount("0.10"))]
        result = totals(rows)
        with self.subTest(case="a"):
            self.assertEqual(Decimal(str(result["a"])), Decimal("0.30"))
        with self.subTest(case="b"):
            self.assertEqual(Decimal(str(result["b"])), Decimal("-0.20"))

    def test_report(self):
        with self.subTest(case="sample"):
            rows = read_rows(ROOT / "data/sample.csv")
            self.assertEqual(format_report(rows), (ROOT / "data/expected.txt").read_text().strip())
        with self.subTest(case="negative with separators"):
            rows = [("z", parse_amount("(1,234.50)")), ("a", parse_amount("1.005"))]
            self.assertEqual(format_report(rows), "a: 1.01\nz: -1,234.50\nTOTAL: -1,233.50")
