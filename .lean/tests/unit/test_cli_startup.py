"""CLI start-up: the status line avoids the gate modules, and bytecode is cached outside the checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import support  # noqa: E402
from lean import progress  # noqa: E402

HEAVY = ("lean.gate", "lean.evidence", "lean.guard")


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE", "XDG_CACHE_HOME", "HOME")}
    env.update(extra)
    return env


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        support.install(self.root)
        self.runtime = self.root / ".agent-runtime"


class StatusLineTests(Fixture):
    def line(self):
        result = support.lean(self.root, "status", "--line", env=clean_env(HOME=str(self.tmp / "home")))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write(self, name, content):
        self.runtime.mkdir(exist_ok=True)
        (self.runtime / name).write_bytes(content if isinstance(content, bytes) else content.encode())

    def test_no_progress_and_no_gate_record(self):
        self.assertEqual(self.line(), "Lean: no task tracked · gate NOT_RUN\n")

    def test_progress_line_is_shown(self):
        state = {"phase": "test", "done": 1, "total": 4, "task": "x"}
        self.write("progress.json", json.dumps(state))
        self.assertEqual(self.line(), f"{progress.line(state)} · gate NOT_RUN\n")

    def test_recorded_pass_is_last_pass_without_verification(self):
        self.write("gate-cache", "anything")
        self.assertEqual(self.line(), "Lean: no task tracked · gate LAST_PASS\n")

    def test_recorded_failure_and_contract_refusal(self):
        self.write("gate-cache", "anything")
        self.write("gate-failed", "f")
        self.assertEqual(self.line(), "Lean: no task tracked · gate FAIL\n")
        self.write("gate-failed", "c refused")
        self.assertEqual(self.line(), "Lean: no task tracked · gate CONTRACT_REFUSED\n")

    def test_unreadable_gate_record_is_unknown(self):
        self.write("gate-failed", b"\xff\xfe\x00")
        self.assertEqual(self.line(), "Lean: no task tracked · gate UNKNOWN\n")

    def test_line_does_not_import_gate_evidence_or_guard(self):
        code = ("import sys; sys.argv=['lean','--root',sys.argv[1],'status','--line']; sys.path.insert(0,'.lean');"
                "sys.dont_write_bytecode=True; from lean.cli import main; main();"
                f"print(sorted(m for m in {HEAVY!r} if m in sys.modules))")
        result = subprocess.run([sys.executable, "-c", code, str(self.root)], cwd=support.ROOT, text=True,
                                capture_output=True, env=clean_env(HOME=str(self.tmp / "home")))
        self.assertEqual(result.stdout.splitlines()[-1], "[]", result.stdout + result.stderr)


class BytecodeCacheTests(Fixture):
    def pycaches(self):
        return [p for p in (self.root / ".lean").rglob("__pycache__")]

    def test_commands_cache_outside_the_checkout(self):
        xdg = self.tmp / "xdg"
        result = support.lean(self.root, "version", env=clean_env(HOME=str(self.tmp / "home"), XDG_CACHE_HOME=str(xdg)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pycaches(), [])
        self.assertTrue(list(xdg.rglob("*.pyc")), "no bytecode cached under XDG_CACHE_HOME")

    def test_home_cache_is_used_without_xdg(self):
        home = self.tmp / "home"
        home.mkdir()
        support.lean(self.root, "version", env=clean_env(HOME=str(home)))
        self.assertEqual(self.pycaches(), [])
        self.assertTrue(list(home.rglob("*.pyc")))

    def test_existing_pycache_prefix_is_respected(self):
        prefix, xdg = self.tmp / "mine", self.tmp / "xdg"
        support.lean(self.root, "version", env=clean_env(PYTHONPYCACHEPREFIX=str(prefix), XDG_CACHE_HOME=str(xdg),
                                                          HOME=str(self.tmp / "home")))
        self.assertTrue(list(prefix.rglob("*.pyc")))
        self.assertFalse(xdg.exists())
        self.assertEqual(self.pycaches(), [])

    def test_unwritable_cache_location_neither_crashes_nor_pollutes_the_checkout(self):
        blocker = self.tmp / "file"
        blocker.write_text("x")
        result = support.lean(self.root, "version", env=clean_env(HOME=str(blocker), XDG_CACHE_HOME=str(blocker)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pycaches(), [])

    def test_relative_home_never_caches_inside_the_working_directory(self):
        # HOME unset with no passwd entry leaves `~` relative; the cache must not land under the cwd.
        result = support.lean(self.root, "version", env=clean_env(HOME="relative-home"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.root.rglob("*.pyc")), [])
        self.assertFalse((self.root / "relative-home").exists())

    def test_a_test_file_run_on_its_own_leaves_the_user_cache_alone(self):
        xdg = self.tmp / "xdg"
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import support; from pathlib import Path;"
                "root = Path(sys.argv[2]); print(support.lean(root, 'version').returncode)")
        result = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]), str(self.root)],
                                text=True, capture_output=True,
                                env=clean_env(HOME=str(self.tmp / "home"), XDG_CACHE_HOME=str(xdg)))
        self.assertEqual(result.stdout.strip(), "0", result.stderr)
        self.assertEqual(list(self.tmp.rglob("*.pyc")), [])

    def refused(self, xdg, elsewhere=()):
        """A cache path another user could control is never used: nothing cached anywhere, nothing in the checkout."""
        result = support.lean(self.root, "version", env=clean_env(HOME=str(self.tmp / "home"), XDG_CACHE_HOME=str(xdg)))
        self.assertEqual(result.returncode, 0, result.stderr)
        for place in (xdg, *elsewhere):
            self.assertEqual(list(Path(place).rglob("*.pyc")), [], place)
        self.assertEqual(self.pycaches(), [])

    def test_symlinked_cache_directory_is_refused(self):
        xdg, planted = self.tmp / "xdg", self.tmp / "planted"
        (xdg / "lean-workflow").mkdir(parents=True, mode=0o700)
        xdg.chmod(0o700)
        planted.mkdir(mode=0o700)
        (xdg / "lean-workflow" / "pycache").symlink_to(planted)
        self.refused(xdg, [planted])

    def test_group_or_world_writable_cache_directory_is_refused(self):
        for mode in (0o770, 0o777):
            with self.subTest(mode=oct(mode)):
                xdg = self.tmp / f"xdg-{mode:o}"
                leaf = xdg / "lean-workflow" / "pycache"
                leaf.mkdir(parents=True, mode=0o700)
                for folder in (xdg, xdg / "lean-workflow"):
                    folder.chmod(0o700)
                leaf.chmod(mode)
                self.refused(xdg)

    def test_symlinked_parent_directory_is_refused(self):
        xdg, planted = self.tmp / "xdg", self.tmp / "planted"
        xdg.mkdir(mode=0o700)
        planted.mkdir(mode=0o700)
        (xdg / "lean-workflow").symlink_to(planted)
        self.refused(xdg, [planted])

    def test_group_writable_cache_base_is_refused(self):
        xdg = self.tmp / "xdg"
        xdg.mkdir()
        xdg.chmod(0o775)  # Another member of the group could swap the directories below it.
        self.refused(xdg)


if __name__ == "__main__":
    unittest.main()
