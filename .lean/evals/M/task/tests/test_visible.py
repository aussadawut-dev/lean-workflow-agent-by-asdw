import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patcher import apply_patch


class Visible(unittest.TestCase):
    def test_replace_one_line(self):
        patch = "--- a/f\n+++ b/f\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n"
        self.assertEqual(apply_patch("a\nb\nc\n", patch), "a\nB\nc\n")


if __name__ == "__main__":
    unittest.main()
