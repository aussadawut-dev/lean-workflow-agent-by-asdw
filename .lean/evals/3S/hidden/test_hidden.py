import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shop.pricing import bulk_discount, line_total
from shop.cart import cart_total


class Hidden(unittest.TestCase):
    def test_discount(self):
        for quantity, expected in ((1, 0.0), (9, 0.0), (10, 5.0), (11, 5.5), (100, 50.0)):
            with self.subTest(quantity=quantity):
                self.assertEqual(bulk_discount(quantity, 5.0), expected)

    def test_totals_unchanged_elsewhere(self):
        for lines, expected in (([(10, 5.0)], 45.0), ([(2, 5.0), (12, 1.0)], 20.8)):
            with self.subTest(lines=lines):
                self.assertEqual(cart_total(lines), expected)
        with self.subTest(case="line_total"):
            self.assertEqual(line_total(3, 2.5), 7.5)
