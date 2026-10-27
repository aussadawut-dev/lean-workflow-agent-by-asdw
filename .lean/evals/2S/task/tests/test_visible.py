import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api


class Visible(unittest.TestCase):
    def test_profile(self):
        self.assertEqual(api.get_profile(1)[0], 200)


if __name__ == "__main__":
    unittest.main()
