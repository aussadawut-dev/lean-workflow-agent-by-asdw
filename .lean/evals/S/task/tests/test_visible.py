import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semver import compare


class Visible(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(compare("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare("1.10.0", "1.9.0"), 1)
        self.assertEqual(compare("1.0.0", "1.0.0"), 0)


if __name__ == "__main__":
    unittest.main()
