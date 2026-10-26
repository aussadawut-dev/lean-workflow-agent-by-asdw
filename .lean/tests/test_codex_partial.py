"""A partial upgrade (Codex hook updated, lean_core.py not copied) must degrade, not crash.

The hook imports the shared refusal core. If a project copies the hook without lean_core.py, the hook used to
die with ImportError before any fallback ran. It must instead keep working: a fresh Stop blocks once, a
continued Stop is released UNVERIFIED (never a pass).
"""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


class PartialUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lean codex partial ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git = ["git", "-C", self.tmp.name, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True, stdin=subprocess.DEVNULL)
        (self.root / "seed.txt").write_text("seed\n")
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")
        shutil.copytree(ROOT / ".lean/scripts", self.root / ".lean/scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "lean_core.py"))
        shutil.copytree(ROOT / ".codex/hooks", self.root / ".codex/hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "commit", "-qm", "init"], check=True, stdin=subprocess.DEVNULL)
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        self.lock = open(runtime / "quality-gate.lock", "w")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(self.lock.close)

    def stop(self, continued):
        done = subprocess.run(
            [sys.executable, str(self.root / ".codex/hooks/quality_gate.py"), "stop", "--root", str(self.root)],
            input=json.dumps({"stop_hook_active": continued}), text=True, capture_output=True)
        return done

    def test_the_fixture_really_lacks_the_core(self):
        self.assertFalse((self.root / ".lean/scripts/lean_core.py").exists())

    def test_missing_core_degrades_instead_of_crashing(self):
        fresh = self.stop(False)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertEqual(json.loads(fresh.stdout)["decision"], "block")
        continued = self.stop(True)
        self.assertEqual(continued.returncode, 0, continued.stderr)
        message = json.loads(continued.stdout)["systemMessage"]
        self.assertIn("UNVERIFIED", message)
        self.assertNotIn("decision", json.loads(continued.stdout))


class FailClosedTests(unittest.TestCase):
    """The Stop path must answer with a block or an UNVERIFIED release for any broken core or internal error."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="lean codex closed ")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git = ["git", "-C", tmp.name, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True, stdin=subprocess.DEVNULL)
        (self.root / "seed.txt").write_text("seed\n")
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")
        shutil.copytree(ROOT / ".lean/scripts", self.root / ".lean/scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".codex/hooks", self.root / ".codex/hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "commit", "-qm", "init"], check=True, stdin=subprocess.DEVNULL)
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        self.lock = open(runtime / "quality-gate.lock", "w")  # a held lock makes every gate run refuse (busy)
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(self.lock.close)

    def core(self, text):
        (self.root / ".lean/scripts/lean_core.py").write_text(text)

    def stop(self, continued, event="stop", session="s1"):
        return subprocess.run(
            [sys.executable, str(self.root / ".codex/hooks/quality_gate.py"), event, "--root", str(self.root)],
            input=json.dumps({"stop_hook_active": continued, "session_id": session}), text=True, capture_output=True,
            stdin=None)

    def assertClosed(self, label):
        fresh, continued = self.stop(False), self.stop(True)
        for done in (fresh, continued):
            self.assertEqual(done.returncode, 0, (label, done.stderr))
            self.assertNotIn("Traceback", done.stderr)
        self.assertEqual(json.loads(fresh.stdout)["decision"], "block", label)
        self.assertIn("UNVERIFIED", json.loads(continued.stdout)["systemMessage"], label)

    def test_core_lacking_gate_refusal(self):
        self.core("BLOCK='block'\nRELEASE_UNCHANGED='release_unchanged'\nRELEASE_CAPPED='release_capped'\n"
                  "def session_key(s):\n    return 'a' * 16\n")
        self.assertClosed("no gate_refusal")

    def test_core_lacking_session_key(self):
        self.core("BLOCK='block'\nRELEASE_UNCHANGED='release_unchanged'\nRELEASE_CAPPED='release_capped'\n"
                  "def gate_refusal(p, c, i, s):\n    return BLOCK, '1'\n")
        fresh = self.stop(False)
        self.assertEqual((fresh.returncode, json.loads(fresh.stdout)["decision"]), (0, "block"), fresh.stderr)
        self.assertTrue((self.root / ".agent-runtime/codex-gate-failed").is_file())  # legacy marker name

    def test_core_raising_at_import(self):
        self.core("raise RuntimeError('half-written core')\n")
        self.assertClosed("raises at import")

    def test_core_whose_functions_raise(self):
        self.core("BLOCK='block'\nRELEASE_UNCHANGED='release_unchanged'\nRELEASE_CAPPED='release_capped'\n"
                  "def session_key(s):\n    raise ValueError('x')\n"
                  "def gate_refusal(p, c, i, s):\n    raise ValueError('y')\n")
        self.assertClosed("functions raise")

    def run_main(self, argv, boom=None):
        import contextlib
        import importlib.util
        import io
        spec = importlib.util.spec_from_file_location("quality_gate_under_test", self.root / ".codex/hooks/quality_gate.py")
        module = importlib.util.module_from_spec(spec)
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["quality_gate.py", *argv, "--root", str(self.root)]), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps({"stop_hook_active": False, "session_id": "s1"}))), \
                contextlib.redirect_stdout(out):
            spec.loader.exec_module(module)
            if boom:
                boom(module)
            code = module.main()
        return code, out.getvalue()

    def test_exception_inside_refuse_is_a_fixed_block(self):
        def boom(module):
            module.refuse = mock.Mock(side_effect=KeyError("injected"))
        code, out = self.run_main(["stop"], boom)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["decision"], "block")
        self.assertEqual(data["reason"], "Codex Quality Gate could not decide; validation NOT_RUN; report BLOCKED")

    GOOD = ("BLOCK='block'\nRELEASE_UNCHANGED='release_unchanged'\nRELEASE_CAPPED='release_capped'\n"
            "def session_key(s):\n    return 'a' * 16\n")

    def assertNeverSilent(self, done, label):
        self.assertFalse(done.returncode == 0 and not done.stdout.strip(), (label, "silent pass", done.stderr))

    def test_core_exiting_zero_at_import_is_not_a_silent_pass(self):
        self.core("raise SystemExit(0)\n")
        self.assertClosed("SystemExit(0) at import")
        for continued in (False, True):
            self.assertNeverSilent(self.stop(continued), "import")

    def test_core_exiting_none_at_import_is_not_a_silent_pass(self):
        self.core("import sys\nsys.exit()\n")
        self.assertClosed("sys.exit() at import")

    def test_gate_refusal_exiting_zero_is_not_a_silent_pass(self):
        self.core(self.GOOD + "def gate_refusal(p, c, i, s):\n    raise SystemExit(0)\n")
        self.assertClosed("gate_refusal SystemExit(0)")
        for continued in (False, True):
            self.assertNeverSilent(self.stop(continued), "gate_refusal")

    def test_session_key_exiting_zero_uses_legacy_names(self):
        self.core("BLOCK='block'\nRELEASE_UNCHANGED='release_unchanged'\nRELEASE_CAPPED='release_capped'\n"
                  "def session_key(s):\n    raise SystemExit(0)\n"
                  "def gate_refusal(p, c, i, s):\n    return BLOCK, '1'\n")
        fresh = self.stop(False)
        self.assertEqual((fresh.returncode, json.loads(fresh.stdout)["decision"]), (0, "block"), fresh.stderr)
        self.assertTrue((self.root / ".agent-runtime/codex-gate-failed").is_file())

    def test_nonzero_exit_from_the_core_is_not_masked(self):
        self.core(self.GOOD + "def gate_refusal(p, c, i, s):\n    raise SystemExit(2)\n")
        done = self.stop(False)
        self.assertEqual(done.returncode, 2, (done.stdout, done.stderr))
        self.assertEqual(done.stdout.strip(), "")

    def test_keyboard_interrupt_is_not_turned_into_a_pass(self):
        self.core(self.GOOD + "def gate_refusal(p, c, i, s):\n    raise KeyboardInterrupt()\n")
        done = self.stop(False)
        self.assertNotEqual(done.returncode, 0, (done.stdout, done.stderr))

    def test_handler_treats_exit_zero_like_an_error_and_keeps_nonzero(self):
        for code in (0, None):
            def boom(module, code=code):
                module.refuse = mock.Mock(side_effect=SystemExit(code))
            out_code, out = self.run_main(["stop"], boom)
            self.assertEqual(out_code, 0)
            data = json.loads(out)
            self.assertEqual((data["decision"], data["reason"]),
                             ("block", "Codex Quality Gate could not decide; validation NOT_RUN; report BLOCKED"))

        def exit2(module):
            module.refuse = mock.Mock(side_effect=SystemExit(2))
        with self.assertRaises(SystemExit) as caught:
            self.run_main(["stop"], exit2)
        self.assertEqual(caught.exception.code, 2)

        def interrupt(module):
            module.refuse = mock.Mock(side_effect=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.run_main(["stop"], interrupt)

    def test_marker_names_accept_only_a_hex_key(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("qg_names", self.root / ".codex/hooks/quality_gate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for bad in ("../../../escape", "AAAAAAAAAAAAAAAA", "a" * 15, "a" * 17, 1234567890123456, None, b"a" * 16):
            module.lean_core = mock.Mock(session_key=lambda _s, bad=bad: bad)
            self.assertEqual(module.marker_names("x"), ("codex-gate-failed", "codex-gate-refusal"), bad)
        module.lean_core = mock.Mock(session_key=lambda _s: "0123456789abcdef")
        self.assertEqual(module.marker_names("x"), ("codex-gate-failed.0123456789abcdef",
                                                    "codex-gate-refusal.0123456789abcdef"))

    BLOCKED_REASON = "Codex Quality Gate could not decide; validation NOT_RUN; report BLOCKED"

    def script(self, name, text):
        (self.root / ".lean/scripts" / name).write_text(text)

    def assertFixedBlock(self, done, label):
        self.assertEqual(done.returncode, 0, (label, done.stdout, done.stderr))
        self.assertNotIn("Traceback", done.stderr, label)
        self.assertEqual(json.loads(done.stdout), {"decision": "block", "reason": self.BLOCKED_REASON}, label)

    def test_shared_module_failing_at_import_blocks_a_stop(self):
        # gate_mode, gate_evidence and contract_guard used to be imported before the fail-closed wrapper existed.
        for name in ("gate_mode.py", "gate_evidence.py", "contract_guard.py"):
            original = (self.root / ".lean/scripts" / name).read_text()
            self.addCleanup(self.script, name, original)
            for label, text in (("ImportError", "raise ImportError('stale')\n"),
                                ("RuntimeError", "raise RuntimeError('half written')\n"),
                                ("SystemExit(0)", "raise SystemExit(0)\n"),
                                ("ValueError", "raise ValueError('bad')\n"),  # would read as invalid input, not a block
                                ("OSError", "raise OSError('gone')\n"),
                                ("syntax", "def broken(:\n")):
                self.script(name, text)
                for continued in (False, True):
                    self.assertFixedBlock(self.stop(continued), (name, label, continued))
            self.script(name, original)

    def test_missing_shared_module_blocks_a_stop(self):
        (self.root / ".lean/scripts/gate_evidence.py").unlink()
        self.assertFixedBlock(self.stop(False), "missing gate_evidence")

    def test_import_failure_keeps_non_zero_exit_and_keyboard_interrupt(self):
        self.script("gate_mode.py", "raise SystemExit(3)\n")
        done = self.stop(False)
        self.assertEqual((done.returncode, done.stdout.strip()), (3, ""), done.stderr)
        self.script("gate_mode.py", "raise KeyboardInterrupt()\n")
        done = self.stop(False)
        self.assertNotEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertNotIn("decision", done.stdout)

    def test_import_failure_does_not_change_session_start_or_run(self):
        self.script("gate_mode.py", "raise ImportError('stale')\n")
        for event in ("session-start", "run"):
            done = self.stop(False, event=event)
            self.assertEqual(done.returncode, 1, (event, done.stdout, done.stderr))
            self.assertIn("ImportError", done.stderr, event)
            self.assertEqual(done.stdout.strip(), "", event)

    def test_working_modules_are_importable_without_side_effects(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("qg_names2", self.root / ".codex/hooks/quality_gate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIsNone(module.IMPORT_FAILURE)
        self.assertTrue(callable(module.state) and hasattr(module.contract_guard, "current"))

    def test_non_stop_events_are_not_wrapped(self):
        def boom(module):
            module.clear_session_refusals = mock.Mock(side_effect=KeyError("injected"))
        with self.assertRaises(KeyError):  # session-start keeps its normal behaviour: no masking
            self.run_main(["session-start"], boom)


if __name__ == "__main__":
    unittest.main()
