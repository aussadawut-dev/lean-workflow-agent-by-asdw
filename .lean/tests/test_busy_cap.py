"""A busy gate lock must not loop the Claude Stop hook: the busy block is counted and capped like any refusal."""
import fcntl
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
           ".lean/scripts/gate_mode.py", ".lean/scripts/contract_guard.py",
           HOOK, ".claude/hooks/session-start.sh", ".gitignore")


# The Claude Stop wrapper as shipped in 4.17.0, which blocked every busy Stop without a cap.
PREVIOUS_WRAPPER = r'''#!/usr/bin/env bash
# Claude Stop adapter; execution and verdicts live in the shared runner.
# A Stop refusal is reported as JSON {"decision":"block"} on exit 0: headless
# `claude -p` only feeds a Stop reason back to the model in that form, and treats
# exit 2 as a hook error. SessionStart seeding keeps the runner's exit codes.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
seed=0
for option in "$@"; do
  [ "$option" != "--seed" ] || seed=1
done

# block <reason>: refuse this Stop with a reason the model sees.
block() {
  printf '%s' "$1" | python3 -c 'import json, sys
reason = sys.stdin.read()[-12000:].strip() or "Lean Quality Gate refused; report BLOCKED and do not declare DONE."
print(json.dumps({"decision": "block", "reason": reason}))' && exit 0
  printf '%s\n' "$1" >&2
  exit 2
}

if [ "$seed" -eq 0 ]; then
  policy="$(python3 "$(dirname "$0")/../../.lean/scripts/gate_mode.py" --root "$root" --check-auto 2>&1)"
  status=$?
  case "$status" in
    0) ;;
    3) if [ -z "${CLAUDE_GATE_FORCE:-}" ]; then printf '%s\n' "$policy" >&2; exit 0; fi ;;
    *) block "$policy" ;;
  esac
fi
runner="$(dirname "$0")/../../.lean/scripts/quality-gate.sh"
[ "$seed" -eq 0 ] || exec "$runner" --claude-hook --root "$root" "$@"

errors="$(mktemp)" || block "Lean Quality Gate could not create a temporary file; validation NOT_RUN."
"$runner" --claude-hook --root "$root" "$@" 2>"$errors"
status=$?
reason="$(cat "$errors")"
rm -f "$errors"
[ "$status" -ne 2 ] || block "$reason"
[ -z "$reason" ] || printf '%s\n' "$reason" >&2
exit "$status"
'''


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

    def test_non_busy_results_are_identical_to_the_previous_wrapper(self):
        outputs = {}
        for label, text in (("old", PREVIOUS_WRAPPER), ("new", None)):
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
