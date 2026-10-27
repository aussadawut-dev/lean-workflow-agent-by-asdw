import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import LRUCache


class Visible(unittest.TestCase):
    def test_basic(self):
        cache = LRUCache(2)
        self.assertEqual(cache.get_or_load("a", lambda: 1), 1)
        self.assertEqual(cache.get("a"), 1)


if __name__ == "__main__":
    unittest.main()
