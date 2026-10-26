"""A busy gate lock must not loop the Claude Stop hook: the busy block is counted and capped like any refusal."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ".claude/hooks/quality-gate.sh"
SCRIPTS = (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
           ".lean/scripts/gate_mode.py", ".lean/scripts/lean_core.py", ".lean/scripts/contract_guard.py",
           HOOK, ".claude/hooks/session-start.sh", ".gitignore")


def head_wrapper():
    return subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{HOOK}"], capture_output=True, text=True,
                          check=True).stdout


class BusyCapTests(unittest.TestCase):
    gate = "true"
    wrapper_text = None  # override the wrapper under test (the previous version, for before/after comparison)

    def make_repo(self, gate=None):
        tmp = tempfile.TemporaryDirectory(prefix="lean busy cap ")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in SCRIPTS:
            if (ROOT / name).exists():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, root / name)
        if self.wrapper_text is not None:
            (root / HOOK).write_text(self.wrapper_text)
        (root / ".lean/PROJECT.md").write_text(f"<!-- gate:start -->\n```sh\n{gate or self.gate}\n```\n<!-- gate:end -->\n")
        (root / ".claude/settings.json").write_text("{}")
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        accepted = subprocess.run(["python3", str(root / ".lean/scripts/gate_evidence.py"), "--root", str(root),
                                   "accept-controls", "--reason", "Fixture"], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        return root

    def stop(self, root, continued, env=None, payload=None):
        data = payload if payload is not None else {"stop_hook_active": continued, "session_id": "s"}
        return subprocess.run(["bash", str(root / HOOK)], input=json.dumps(data), text=True, capture_output=True,
                              timeout=30, env={**os.environ, "CLAUDE_PROJECT_DIR": str(root), **(env or {})})

    def marker(self, root):
        # The wrapper keys the marker by session; the previous wrapper (HEAD) used the un-keyed name.
        key = hashlib.sha256(b"s").hexdigest()[:16]
        path = root / f".agent-runtime/gate-failed.{key}"
        if not path.exists():
            path = root / ".claude/.gate-failed"
        return path.read_text() if path.exists() else None

    def held(self, root):
        (root / ".agent-runtime").mkdir(exist_ok=True)
        lock = (root / ".agent-runtime/quality-gate.lock").open("w")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock

    def kind(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        if data.get("decision") == "block":
            self.assertIn("Quality Gate busy", data["reason"])
            return "block"
        self.assertIn("UNVERIFIED", data["systemMessage"])
        self.assertIn("busy", data["systemMessage"])
        return "release"

    def assert_no_pass_records(self, root):
        self.assertFalse((root / ".claude/.gate-cache").exists())
        self.assertFalse((root / ".agent-runtime/gate-receipt").exists())
        self.assertFalse((root / "runs").exists())

    def test_busy_blocks_three_times_then_releases_unverified(self):
        root = self.make_repo("printf ran >> runs")
        lock = self.held(root)
        kinds, markers = [], []
        for index in range(6):
            kinds.append(self.kind(self.stop(root, index > 0)))
            markers.append(self.marker(root))
        self.assertEqual(kinds, ["block"] * 3 + ["release"] * 3)
        self.assertEqual(markers, ["1", "2", "3", "4", "5", "6"])
        self.assert_no_pass_records(root)
        self.assertEqual([p.name for p in (root / ".agent-runtime").iterdir() if "receipt" in p.name], [])
        lock.close()

    def test_normal_pass_after_busy_clears_the_counter(self):
        root = self.make_repo()
        lock = self.held(root)
        for index in range(5):
            self.kind(self.stop(root, index > 0))
        self.assertEqual(self.marker(root), "5")
        fcntl.flock(lock, fcntl.LOCK_UN)
        result = self.stop(root, True)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ""), result.stderr)
        self.assertIsNone(self.marker(root))

    def test_fresh_stop_after_cap_release_restarts_the_count(self):
        root = self.make_repo()
        self.held(root)
        for index in range(5):
            self.kind(self.stop(root, index > 0))
        self.assertEqual(self.kind(self.stop(root, False)), "block")
        self.assertEqual(self.marker(root), "1")

    def test_malformed_payload_counts_as_fresh(self):
        root = self.make_repo()
        self.held(root)
        for _ in range(3):
            self.assertEqual(self.kind(self.stop(root, False, payload={"stop_hook_active": "yes"})), "block")
        self.assertEqual(self.marker(root), "1")

    def test_unavailable_core_falls_back(self):
        root = self.make_repo()
        shim = root.parent / (root.name + " bin")
        shim.mkdir()
        self.addCleanup(shutil.rmtree, shim, True)
        (shim / "python3").write_text(f'#!/bin/sh\n[ "$1" = "-c" ] && [ -n "$LEAN_SHIM_CORE" ] && '
                                      f'case "$2" in *lean_core*) exit 1;; esac\nexec "{shutil.which("python3")}" "$@"\n')
        (shim / "python3").chmod(0o755)
        env = {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "LEAN_SHIM_CORE": "1"}
        self.held(root)
        self.assertEqual(self.kind(self.stop(root, False, env)), "block")
        self.assertEqual(self.marker(root), "1")
        self.assertEqual(self.kind(self.stop(root, True, env)), "release")
        self.assertEqual(self.marker(root), "4")

    def message(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        return data.get("systemMessage") if data.get("decision") != "block" else "block: " + data["reason"]

    def make_lock_unavailable(self, root):
        (root / ".agent-runtime").mkdir(exist_ok=True)
        (root / ".agent-runtime/quality-gate.lock").mkdir()  # opening a directory for the lock fails

    def test_lock_unavailable_releases_with_its_own_wording(self):
        root = self.make_repo()
        self.make_lock_unavailable(root)
        first = self.message(self.stop(root, False))
        self.assertTrue(first.startswith("block: Quality Gate lock unavailable"), first)
        for _ in range(2):
            self.assertTrue(self.message(self.stop(root, True)).startswith("block: "))
        released = self.message(self.stop(root, True))
        self.assertEqual(released, "Lean Quality Gate could not take its lock (gate lock unavailable in this checkout) "
                                   "after 3 attempts; Stop released UNVERIFIED. Validation did not run, so the work "
                                   "is not DONE; report BLOCKED.")
        self.assertNotIn("busy", released)

    def test_busy_release_wording_is_unchanged(self):
        root = self.make_repo()
        self.held(root)
        self.stop(root, False)
        self.stop(root, True)
        self.stop(root, True)
        self.assertEqual(self.message(self.stop(root, True)),
                         "Lean Quality Gate stayed busy (another gate is running in this checkout) after 3 attempts; "
                         "Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED.")

    def test_unusable_marker_releases_a_continued_busy_stop(self):
        root = self.make_repo()
        self.held(root)
        key = hashlib.sha256(b"s").hexdigest()[:16]
        (root / f".agent-runtime/gate-failed.{key}").mkdir()
        self.assertEqual(self.kind(self.stop(root, False)), "block")
        self.assertEqual(self.kind(self.stop(root, True)), "release")

    def test_unusable_runtime_keeps_the_count_in_the_legacy_marker(self):
        root = self.make_repo()
        lock = self.held(root)
        lock.close()
        shutil.rmtree(root / ".agent-runtime")
        (root / ".agent-runtime").write_text("not a directory")
        # No lock can be taken, so the wrapper sees "lock unavailable"; the count still reaches 3.
        kinds = []
        for index in range(5):
            result = self.stop(root, index > 0)
            self.assertEqual(result.returncode, 0, result.stderr)
            kinds.append("block" if json.loads(result.stdout).get("decision") == "block" else "release")
        self.assertEqual(kinds, ["block"] * 3 + ["release"] * 2)
        self.assertEqual((root / ".claude/.gate-failed").read_text(), "5")

    def test_non_busy_results_are_identical_to_the_previous_wrapper(self):
        outputs = {}
        for label, text in (("old", head_wrapper()), ("new", None)):
            type(self).wrapper_text = text
            try:
                failing = self.make_repo("echo boom >&2; false")
                passing = self.make_repo("true")
            finally:
                type(self).wrapper_text = None
            steps = []
            for repo, continued in ((failing, False), (failing, True), (passing, False)):
                result = self.stop(repo, continued)
                steps.append((result.returncode, result.stdout, result.stderr.replace(str(repo), "ROOT"),
                              self.marker(repo)))
            outputs[label] = steps
        self.assertEqual(outputs["old"], outputs["new"])
        self.assertEqual(outputs["new"][0][3], "1")
        self.assertEqual(json.loads(outputs["new"][0][1])["decision"], "block")
        self.assertIsNone(outputs["new"][2][3])


if __name__ == "__main__":
    unittest.main()
