import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs


class Visible(unittest.TestCase):
    def test_jobs(self):
        self.assertEqual(len(jobs.run_batch(range(5))), 5)


if __name__ == "__main__":
    unittest.main()
