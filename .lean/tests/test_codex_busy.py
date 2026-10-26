"""Codex Stop counts a busy gate lock like Claude's busy_stop: capped, never released as unchanged."""
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".codex/hooks/quality_gate.py"
BUSY = "Quality Gate busy: another gate is running in this checkout; validation NOT_RUN. Retry after it finishes.\n"


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lean codex busy ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git = ["git", "-C", self.tmp.name, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True, stdin=subprocess.DEVNULL)
        (self.root / "seed.txt").write_text("seed\n")
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")
        shutil.copytree(ROOT / ".lean/scripts", self.root / ".lean/scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".codex/hooks", self.root / ".codex/hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run([*git, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run([*git, "commit", "-qm", "init"], check=True, stdin=subprocess.DEVNULL)
        self.runtime = self.root / ".agent-runtime"
        self.runtime.mkdir(exist_ok=True)

    def stop(self, continued):
        """One real Stop of the copied hook; returns its parsed JSON output."""
        done = subprocess.run(
            [sys.executable, str(self.root / ".codex/hooks/quality_gate.py"), "stop", "--root", str(self.root)],
            input=json.dumps({"stop_hook_active": continued}), text=True, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def hold_lock(self):
        handle = open(self.runtime / "quality-gate.lock", "w")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(handle.close)
        return handle


class BusyStopTests(Fixture):
    def test_six_stops_block_three_then_release_unverified(self):
        self.hold_lock()
        outputs = [self.stop(index > 0) for index in range(6)]
        for index, out in enumerate(outputs[:3]):
            self.assertEqual(out.get("decision"), "block", (index, out))
            self.assertIn("Quality Gate busy", out["reason"])
        for out in outputs[3:]:
            self.assertNotIn("decision", out)
            self.assertIn("stayed busy", out["systemMessage"])
            self.assertIn("UNVERIFIED", out["systemMessage"])
            self.assertNotIn("passed", out["systemMessage"])
        self.assertEqual((self.runtime / "codex-gate-failed").read_text(), "6")
        self.assertFalse((self.runtime / "codex-gate-refusal").exists())

    def test_fresh_stop_restarts_the_count(self):
        self.hold_lock()
        for continued in (False, True, True, True):
            self.stop(continued)
        self.assertEqual(self.stop(False).get("decision"), "block")
        self.assertEqual((self.runtime / "codex-gate-failed").read_text(), "1")

    def test_lock_unavailable_counts_the_same(self):
        hook = load_file("codex_busy_unavail", HOOK)
        fake = subprocess.CompletedProcess([], 2, stdout="", stderr="Quality Gate lock unavailable: x; validation NOT_RUN.\n")
        decisions = self.run_main(hook, fake, [False, True, True, True])
        self.assertEqual([d.get("decision") for d in decisions], ["block"] * 3 + [None])
        self.assertIn("gate lock unavailable", decisions[3]["systemMessage"])
        self.assertNotIn("stayed busy", decisions[3]["systemMessage"])
        self.assertIn("UNVERIFIED", decisions[3]["systemMessage"])

    def run_main(self, hook, fake, sequence, session=None):
        results = []
        for continued in sequence:
            payload = {"stop_hook_active": continued}
            if session:
                payload["session_id"] = session
            out = io.StringIO()
            with mock.patch.object(sys, "argv", ["h", "stop", "--root", str(self.root)]), \
                    mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                    mock.patch.object(hook.subprocess, "run", return_value=fake), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(hook.main(), 0)
            results.append(json.loads(out.getvalue()))
        return results

    def test_lock_released_then_pass_clears_markers(self):
        handle = self.hold_lock()
        self.stop(False)
        self.assertTrue((self.runtime / "codex-gate-failed").exists())
        fcntl.flock(handle, fcntl.LOCK_UN)
        hook = load_file("codex_busy_pass", HOOK)
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        (out,) = self.run_main(hook, ok, [True])
        self.assertIn("checks passed", out["systemMessage"])
        self.assertFalse((self.runtime / "codex-gate-failed").exists())
        self.assertFalse((self.runtime / "codex-gate-refusal").exists())

    def test_busy_with_session_never_writes_or_uses_the_fingerprint(self):
        hook = load_file("codex_busy_session", HOOK)
        (self.runtime / "codex-gate-refusal").write_text("stale")
        busy = subprocess.CompletedProcess([], 2, stdout="", stderr=BUSY)
        with mock.patch.object(hook.contract_guard, "current", return_value="Contract: trivial (x)"):
            outs = self.run_main(hook, busy, [False, True, True, True, True], session="s")
        self.assertEqual([d.get("decision") for d in outs], ["block"] * 3 + [None, None])
        self.assertEqual((self.runtime / "codex-gate-refusal").read_text(), "stale")

    def test_unwritable_runtime_falls_back_like_refuse(self):
        hook = load_file("codex_busy_fallback", HOOK)
        shutil.rmtree(self.runtime)
        target = self.root / "elsewhere"
        target.mkdir()
        self.runtime.symlink_to(target)
        busy = subprocess.CompletedProcess([], 2, stdout="", stderr=BUSY)
        first, second = self.run_main(hook, busy, [False, True])
        self.assertEqual(first.get("decision"), "block")
        self.assertIn("stayed busy", second["systemMessage"])
        self.assertFalse(any(target.iterdir()))


    def test_unusable_marker_path_releases_a_continued_stop(self):
        # A refusal marker that is a directory (or FIFO) cannot be read or written; it used to block forever.
        hook = load_file("codex_busy_dirmarker", HOOK)
        for kind in ("directory", "fifo"):
            shutil.rmtree(self.runtime, ignore_errors=True)
            self.runtime.mkdir()
            marker = self.runtime / "codex-gate-failed"
            if kind == "directory":
                marker.mkdir()
            else:
                os.mkfifo(marker)
            for fake in (subprocess.CompletedProcess([], 2, stdout="", stderr=BUSY),
                         subprocess.CompletedProcess([], 1, stdout="", stderr="boom")):
                first, second, third = self.run_main(hook, fake, [False, True, True])
                self.assertEqual(first.get("decision"), "block", (kind, first))
                for out in (second, third):
                    self.assertNotIn("decision", out, (kind, out))
                    self.assertIn("UNVERIFIED", out["systemMessage"])

    def test_lock_unavailable_wording_is_not_the_busy_wording(self):
        hook = load_file("codex_busy_wording", HOOK)
        busy = subprocess.CompletedProcess([], 2, stdout="", stderr=BUSY)
        unavailable = subprocess.CompletedProcess([], 2, stdout="", stderr="Quality Gate lock unavailable: x; validation NOT_RUN.\n")
        (_, _, _, released_busy) = self.run_main(hook, busy, [False, True, True, True])
        (_, _, _, released_other) = self.run_main(hook, unavailable, [False, True, True, True])
        self.assertEqual(released_busy["systemMessage"], "Codex Quality Gate stayed busy (another gate is running in this checkout) after 3 attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED.")
        self.assertNotIn("busy", released_other["systemMessage"])
        self.assertIn("gate lock unavailable", released_other["systemMessage"])

    def test_malformed_session_id_stops_are_bounded(self):
        hook = load_file("codex_busy_badsession", HOOK)
        fail = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
        for bad in ("a\nb", 5, None, ["x"], {"k": 1}):
            shutil.rmtree(self.runtime, ignore_errors=True)
            outs = []
            for continued in (False, True, True, True, True):
                out = io.StringIO()
                payload = {"stop_hook_active": continued, "session_id": bad}
                with mock.patch.object(sys, "argv", ["h", "stop", "--root", str(self.root)]), \
                        mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                        mock.patch.object(hook.subprocess, "run", return_value=fail), \
                        contextlib.redirect_stdout(out):
                    self.assertEqual(hook.main(), 0)
                outs.append(json.loads(out.getvalue()))
            self.assertEqual([o.get("decision") for o in outs], ["block"] * 3 + [None, None], bad)


class NonBusyUnchangedTests(Fixture):
    """The new hook and HEAD's hook must decide identically for every non-busy failure."""

    def head_hook(self):
        shown = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:.codex/hooks/quality_gate.py"],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if shown.returncode != 0:
            self.skipTest("no HEAD version of the hook")
        self.old_tmp = tempfile.TemporaryDirectory(prefix="lean codex head ")
        self.addCleanup(self.old_tmp.cleanup)
        base = Path(self.old_tmp.name)
        (base / ".codex/hooks").mkdir(parents=True)
        (base / ".codex/hooks/quality_gate.py").write_text(shown.stdout)
        (base / ".lean").mkdir()
        (base / ".lean/scripts").symlink_to(ROOT / ".lean/scripts")
        return load_file("codex_head_hook", base / ".codex/hooks/quality_gate.py")

    def sequence(self, hook):
        steps = [(False, "a"), (True, "a"), (False, "a"), (True, "b"), (True, "b"), (True, "c"), (True, "d"), (True, "e")]
        failures = [
            subprocess.CompletedProcess([], 1, stdout="", stderr="boom"),
            subprocess.CompletedProcess([], 2, stdout="", stderr="Gate failed: Quality Gate busy is only mentioned"),
            subprocess.CompletedProcess([], 1, stdout="", stderr="Quality Gate busy: but exit 1"),
        ]
        log = []
        for fake in failures:
            shutil.rmtree(self.runtime, ignore_errors=True)
            for continued, change in steps:
                (self.root / "work.txt").write_text(change)
                out = io.StringIO()
                payload = {"stop_hook_active": continued, "session_id": "s"}
                with mock.patch.object(sys, "argv", ["h", "stop", "--root", str(self.root)]), \
                        mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                        mock.patch.object(hook.contract_guard, "current", return_value="Contract: trivial (x)"), \
                        mock.patch.object(hook.subprocess, "run", side_effect=self.runner(hook, fake)), \
                        contextlib.redirect_stdout(out):
                    code = hook.main()
                log.append((code, out.getvalue(), self.markers()))
        # Contract refusals (no declared contract, work changed).
        shutil.rmtree(self.runtime, ignore_errors=True)
        for continued in (False, True, True, True, True):
            out = io.StringIO()
            payload = {"stop_hook_active": continued, "session_id": "s"}
            with mock.patch.object(sys, "argv", ["h", "stop", "--root", str(self.root)]), \
                    mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                    mock.patch.object(hook.contract_guard, "current", return_value=""), \
                    contextlib.redirect_stdout(out):
                code = hook.main()
            log.append((code, out.getvalue(), self.markers()))
        return log

    def runner(self, hook, fake):
        real = subprocess.run

        def run(command, *args, **kwargs):
            return fake if "quality-gate.sh" in " ".join(map(str, command)) else real(command, *args, **kwargs)
        return run

    def markers(self):
        # The new hook keys these files by session; the HEAD hook used the un-keyed names.
        key = hashlib.sha256(b"s").hexdigest()[:16]
        found = {}
        for name in ("codex-gate-failed", "codex-gate-refusal"):
            path = next((p for p in (self.runtime / f"{name}.{key}", self.runtime / name) if p.exists()), None)
            found[name] = path.read_text() if path else None
        return found

    def test_decisions_and_markers_match_head(self):
        old = self.head_hook()
        new = load_file("codex_new_hook", HOOK)
        expected = self.sequence(old)
        actual = self.sequence(new)
        self.assertEqual(actual, expected)
        self.assertTrue(any("nothing changed" in text for _, text, _ in expected))
        self.assertTrue(any("still refused after" in text for _, text, _ in expected))
        self.assertTrue(any("no declared Task Contract" in text for _, text, _ in expected))


if __name__ == "__main__":
    unittest.main()
