import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report.parse import parse_amount


class Visible(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(float(parse_amount("12.50")), 12.5)


if __name__ == "__main__":
    unittest.main()
