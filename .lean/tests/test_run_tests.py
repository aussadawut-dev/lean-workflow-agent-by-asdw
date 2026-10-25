"""The parallel runners must report every failure and fail when any part fails."""
import shutil
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "run_tests.py"
HOOKS = Path(__file__).resolve().parent / "test-hooks.sh"
ROOT = Path(__file__).resolve().parents[2]

PASSING = "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
FAILING = "import unittest\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('planted failure')\n"
# Each test records its name, so a run shows which tests ran and how often.
LOGGING = ("import unittest\nfrom pathlib import Path\nLOG = Path(__file__).with_name('ran.log')\n"
           "class T(unittest.TestCase):\n"
           + "".join(f"    def test_{n}(self):\n        with LOG.open('a') as log:\n            log.write('test_{n}\\n')\n"
                     for n in range(5)))
MIXED = ("import unittest\nclass T(unittest.TestCase):\n"
         "    def test_a(self):\n        pass\n"
         "    def test_b(self):\n        self.fail('planted failure')\n"
         "    def test_c(self):\n        pass\n")
BROKEN = "raise ImportError('planted import failure')\n"


class ParallelRunnerTests(unittest.TestCase):
    def run_in(self, files, *extra):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.start = Path(directory.name) / ".lean/tests"
        self.start.mkdir(parents=True)
        for name, body in files.items():
            (self.start / name).write_text(body)
        return subprocess.run([sys.executable, str(RUNNER), "--start-dir", str(self.start), *extra],
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

    def test_completed_failure_is_reported_while_first_job_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            start = Path(directory) / ".lean/tests"
            start.mkdir(parents=True)
            release = start / "release"
            entered = start / "entered"
            slow = ("import time, unittest\nfrom pathlib import Path\n"
                    "class T(unittest.TestCase):\n"
                    " def test_slow(self):\n"
                    "  base = Path(__file__).parent\n"
                    "  (base / 'entered').touch()\n"
                    "  deadline = time.monotonic() + 30\n"
                    "  while not (base / 'release').exists():\n"
                    "   if time.monotonic() > deadline: self.fail('release timed out')\n"
                    "   time.sleep(0.01)\n")
            for name, body in {"test_a.py": slow, "test_b.py": FAILING, "test_c.py": PASSING}.items():
                (start / name).write_text(body)
            process = subprocess.Popen([sys.executable, str(RUNNER), "--start-dir", str(start), "-j", "2"],
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            lines = queue.Queue()
            output = []

            def read_output():
                for line in process.stdout:
                    output.append(line)
                    lines.put(line)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            early = []
            try:
                deadline = time.monotonic() + 10
                while not entered.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(entered.exists(), "slow job never entered its barrier")
                # A generous timeout detects missing feedback; timing is not the acceptance metric.
                deadline = time.monotonic() + 10
                while not any(line.startswith("FAIL") and "test_b.py" in line for line in early):
                    early.append(lines.get(timeout=max(0.01, deadline - time.monotonic())))
                self.assertIsNone(process.poll(), "runner exited while first job was blocked")
                self.assertFalse(release.exists())
            except queue.Empty:
                self.fail("completed failure was hidden behind the blocked first job")
            finally:
                release.touch()
                try:
                    process.wait(timeout=15)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    reader.join(timeout=5)
                    process.stdout.close()
            result = "".join(output)
            self.assertEqual(process.returncode, 1, result)
            self.assertIn("test_a.py", result)
            self.assertIn("test_c.py", result)  # A failure must not cancel pending work.
            self.assertIn("===== test_b.py =====", result)
            self.assertIn("test_b.py: FAIL: test_bad", result)
            self.assertTrue(result.rstrip().endswith("FAILED (1)"), result)

    def test_named_missing_file_is_not_success(self):
        # unittest discover exits 0 for a pattern that matches nothing on Python < 3.12.
        result = self.run_in({"test_a.py": PASSING}, "test_typo.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("test_typo.py", result.stderr)

    def test_empty_directory_is_not_success(self):
        result = self.run_in({})
        self.assertEqual(result.returncode, 1)
        self.assertIn("no test files", result.stderr)

    def test_shards_run_every_test_exactly_once(self):
        result = self.run_in({"test_many.py": LOGGING}, "--shards", "3", "test_many.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sorted((self.start / "ran.log").read_text().split()), [f"test_{n}" for n in range(5)])
        self.assertIn("test_many.py [3/3]", result.stdout)
        self.assertIn("1 files (3 processes)", result.stdout)

    def test_shards_never_exceed_the_tests_in_a_file(self):
        result = self.run_in({"test_a.py": PASSING}, "--shards", "4")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("[1/", result.stdout)
        self.assertIn("1 files in", result.stdout)

    def test_a_failing_shard_fails_the_run_and_shows_its_output(self):
        result = self.run_in({"test_mixed.py": MIXED}, "--shards", "3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("planted failure", result.stdout)
        self.assertIn("FAILED (1)", result.stdout)

    def test_a_file_that_cannot_import_still_fails_when_sharded(self):
        result = self.run_in({"test_broken.py": BROKEN, "test_a.py": PASSING}, "--shards", "2")
        self.assertEqual(result.returncode, 1)
        self.assertIn("planted import failure", result.stdout)
        self.assertIn("===== test_broken.py =====", result.stdout)

    def test_named_shell_suite_runs_with_bash(self):
        passing = self.run_in({"suite.sh": "echo suite ran\n"}, "suite.sh")
        self.assertEqual(passing.returncode, 0, passing.stdout + passing.stderr)
        self.assertIn("ok", passing.stdout)
        failing = self.run_in({"suite.sh": "echo planted shell failure\nexit 3\n"}, "suite.sh")
        self.assertEqual(failing.returncode, 1)
        self.assertIn("===== suite.sh =====", failing.stdout)
        self.assertIn("planted shell failure", failing.stdout)

    def test_every_failed_name_is_repeated_after_the_failure_blocks(self):
        # A gate shows only its output's last 40 lines, so names from every failed job must end it.
        suite = "echo 'FAIL hook case one'\necho 'ok   hook case two'\nexit 1\n"
        result = self.run_in({"suite.sh": suite, "test_b.py": FAILING}, "suite.sh", "test_b.py")
        self.assertEqual(result.returncode, 1)
        out = result.stdout
        recap_at = out.find("\nFailed tests:\n")
        self.assertGreater(recap_at, out.rindex("===== "), out)
        recap = out[recap_at:].splitlines()
        self.assertIn("suite.sh: FAIL hook case one", recap)
        self.assertTrue(any(line.startswith("test_b.py: FAIL: test_bad") for line in recap), recap)
        self.assertFalse(any("hook case two" in line for line in recap), recap)
        self.assertTrue(out.rstrip().endswith("FAILED (2)"))

    def test_shards_must_be_positive(self):
        result = self.run_in({"test_a.py": PASSING}, "--shards", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--shards", result.stderr)


class HookSuiteReportTests(unittest.TestCase):
    """test-hooks.sh runs its parts concurrently; every failure must still count and be listed last."""

    def run_against(self, gate_evidence):
        """Run the real hook suite against stub hooks whose gate always passes silently."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        stubs = {".claude/hooks/quality-gate.sh": "#!/usr/bin/env bash\nexit 0\n",
                 ".claude/hooks/session-start.sh": "#!/usr/bin/env bash\nexit 0\n",
                 ".lean/scripts/gate_evidence.py": gate_evidence,
                 ".lean/scripts/contract_guard.py": "import sys\nsys.exit(0)\n"}
        for name, body in stubs.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(body)
        (root / ".lean/tests").mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOKS, root / ".lean/tests/test-hooks.sh")
        shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
        return subprocess.run(["bash", str(root / ".lean/tests/test-hooks.sh")], text=True, capture_output=True)

    def test_failed_cases_are_counted_and_listed_last(self):
        result = self.run_against("import sys\nsys.exit(0)\n")
        self.assertNotEqual(result.returncode, 0)
        head, marker, tail = result.stdout.rpartition("Failed cases:\n")
        self.assertTrue(marker, result.stdout[-2000:])
        failed = [line for line in head.splitlines() if line.startswith("FAIL ")]
        self.assertTrue(failed)
        self.assertEqual(tail.splitlines(), failed)
        self.assertRegex(head.splitlines()[-1], rf"^\d+ passed, {len(failed)} failed$")

    def test_a_part_that_stops_early_is_a_failure(self):
        # Without accepted controls run_gate returns before setting $code, and set -u stops the part.
        result = self.run_against("import sys\nsys.exit(1)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stopped before its last case", result.stdout)
        self.assertRegex(result.stdout, r"\n0 passed, [1-9]\d* failed\n")


if __name__ == "__main__":
    unittest.main()
