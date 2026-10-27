import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shop.cart import cart_total


class Visible(unittest.TestCase):
    def test_small_cart(self):
        self.assertEqual(cart_total([(2, 5.0)]), 10.0)


if __name__ == "__main__":
    unittest.main()
