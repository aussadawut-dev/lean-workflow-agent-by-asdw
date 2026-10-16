"""The parallel runner must report every file and fail when any file fails."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "run_tests.py"

PASSING = "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
FAILING = "import unittest\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('planted failure')\n"


class ParallelRunnerTests(unittest.TestCase):
    def run_in(self, files, *extra):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        start = Path(directory.name) / ".lean/tests"
        start.mkdir(parents=True)
        for name, body in files.items():
            (start / name).write_text(body)
        return subprocess.run([sys.executable, str(RUNNER), "--start-dir", str(start), *extra],
                              text=True, capture_output=True)

    def test_all_passing_files_exit_zero(self):
        result = self.run_in({"test_a.py": PASSING, "test_b.py": PASSING}, "-j", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertIn("2 files", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("OK"))

    def test_one_failing_file_fails_run_and_shows_its_output(self):
        result = self.run_in({"test_a.py": PASSING, "test_b.py": FAILING, "helper.py": FAILING})
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertIn("===== test_b.py =====", result.stdout)
        self.assertIn("planted failure", result.stdout)
        self.assertIn("2 files", result.stdout)
        self.assertIn("FAILED (1)", result.stdout)

    def test_named_missing_file_is_not_success(self):
        # unittest discover exits 0 for a pattern that matches nothing on Python < 3.12.
        result = self.run_in({"test_a.py": PASSING}, "test_typo.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("test_typo.py", result.stderr)

    def test_empty_directory_is_not_success(self):
        result = self.run_in({})
        self.assertEqual(result.returncode, 1)
        self.assertIn("no test files", result.stderr)


if __name__ == "__main__":
    unittest.main()
