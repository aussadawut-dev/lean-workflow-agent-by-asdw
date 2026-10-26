"""A marked pending review quiets Stops refused only for its missing receipt, never passing them."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean, stop_refusal  # noqa: E402
from lean import gate  # noqa: E402

CONTRACT = "Contract: risk=HIGH quality=HIGH acceptance=fixture checks pass"
OTHER = "Contract: risk=HIGH quality=HIGH acceptance=another task"
DECLARE = "python3 .lean/bin/lean contract declare --contract '{}'"


def environment(root):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    env.pop("LEAN_GATE_FORCE", None)
    env.pop("LEAN_GATE_LOCK_FD", None)
    return env


class ReviewPendingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean review pending ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        # An ignored flag decides pass or fail, so a failing check leaves the shipping state unchanged.
        self.flag = self.root / ".agent-runtime/pass"
        (self.root / ".lean/PROJECT.md").write_text(
            "<!-- gate:start -->\n```sh\ntest -f .agent-runtime/pass\n```\n<!-- gate:end -->\n")
        (self.root / ".claude/settings.json").write_text("{}")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.flag.parent.mkdir(exist_ok=True)
        self.flag.write_text("")
        self.assertEqual(lean(self.root, "gate", "run", env=environment(self.root)).returncode, 0)  # Records controls.
        (self.root / "work.txt").write_text("change\n")
        self.marker = self.root / ".agent-runtime/review-pending.json"
        self.cache = self.root / ".agent-runtime/gate-cache"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                               *args], check=True, text=True, capture_output=True).stdout.strip()

    def bind(self, session, contract=CONTRACT):
        bound = lean(self.root, "hook", "claude", "pre-tool",
                     input=json.dumps({"session_id": session, "tool_name": "Bash",
                                       "tool_input": {"command": DECLARE.format(contract)}}))
        self.assertEqual(bound.returncode, 0, bound.stderr)

    def stop(self, provider, session, active=False):
        """The Stop command exactly as the shipped provider configuration runs it."""
        name = ".claude/settings.json" if provider == "claude" else ".codex/hooks.json"
        command = json.loads((ROOT / name).read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
        payload = {"session_id": session, "stop_hook_active": active}
        return stop_refusal(subprocess.run(["bash", "-c", command], cwd=self.root, input=json.dumps(payload),
                                           text=True, capture_output=True, env=environment(self.root)))

    def record(self, verdict, contract=CONTRACT):
        helper = [sys.executable, str(self.root / ".lean/bin/lean"), "--root", str(self.root), "evidence"]
        snapshot = subprocess.run(helper + ["state"], text=True, capture_output=True).stdout.strip()
        recorded = subprocess.run(helper + ["record-review", "--contract", contract, "--reviewer", "independent-test",
                                            "--evidence", "fixture", "--verdict", verdict, "--state", snapshot],
                                  text=True, capture_output=True)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)

    def touch(self):
        """Change the shipping state, so an earlier refusal is not merely shown again."""
        self.changes = getattr(self, "changes", 0) + 1
        (self.root / "work.txt").write_text(f"change {self.changes}\n")

    def assert_released(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        message = json.loads(result.stdout)["systemMessage"]
        self.assertIn("review pending since", message)
        self.assertIn("UNVERIFIED", message)
        self.assertIn("not DONE", message)
        self.assertFalse(self.cache.exists(), "a pending release must never record a pass")
        self.assertNotIn("PASS", lean(self.root, "gate", "status").stdout)

    def assert_blocked(self, result, text="review"):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(text, result.stderr.lower())

    def adapters(self):
        for provider in ("claude", "codex"):
            with self.subTest(adapter=provider):
                session = f"{provider}-s"
                self.bind(session)
                yield provider, session

    def test_a_marked_pending_review_releases_every_stop_without_a_pass(self):
        for provider, session in self.adapters():
            self.marker.unlink(missing_ok=True)
            self.assert_blocked(self.stop(provider, session))
            gate.mark_review_pending(self.root, CONTRACT, session)
            # Repeated Stops while the reviewer runs are released, not counted towards the refusal cap.
            for attempt in range(gate.MAX_REFUSALS + 2):
                self.assert_released(self.stop(provider, session, active=attempt > 0))
            # A direct run is not a Stop: it still reports the missing receipt.
            direct = lean(self.root, "gate", "run", "--contract", CONTRACT, "--session", session,
                          env=environment(self.root))
            self.assertEqual(direct.returncode, 2, direct.stderr)

    def test_the_cli_marks_a_pending_review_and_the_guard_keeps_it_out_of_hand_edits(self):
        self.bind("cli-s")
        marked = lean(self.root, "gate", "review-pending", "--contract", CONTRACT, "--session", "cli-s")
        self.assertEqual(marked.returncode, 0, marked.stderr)
        self.assertEqual(json.loads(self.marker.read_text())["session"], "cli-s")
        self.assert_released(self.stop("claude", "cli-s", active=False))
        refused = lean(self.root, "gate", "review-pending", "--contract", "not a contract", "--session", "cli-s")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        # Only the command writes the marker: an edit tool or shell write to it is denied like the receipt.
        marker = ".agent-runtime/review-pending.json"
        for name, tool_input in (("Write", {"file_path": f"{self.root}/{marker}"}),
                                 ("Bash", {"command": f"echo '{{}}' > {marker}"})):
            with self.subTest(name=name):
                result = lean(self.root, "hook", "claude", "pre-tool",
                              input=json.dumps({"session_id": "cli-s", "tool_name": name, "tool_input": tool_input}))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("lean gate review-pending", result.stderr)
        read = lean(self.root, "hook", "claude", "pre-tool",
                    input=json.dumps({"session_id": "cli-s", "tool_name": "Bash",
                                      "tool_input": {"command": f"cat {marker}"}}))
        self.assertEqual(read.returncode, 0, read.stderr)

    def test_the_marker_records_contract_state_session_and_time(self):
        before = time.time()
        marker = gate.mark_review_pending(self.root, CONTRACT, "s")
        stored = json.loads(self.marker.read_text())
        self.assertEqual(stored, marker)
        self.assertEqual(stored["schema"], 1)
        self.assertEqual(stored["contract"], CONTRACT)
        self.assertEqual(stored["session"], "s")
        self.assertEqual(stored["state"], lean(self.root, "evidence", "state").stdout.strip())
        self.assertGreaterEqual(stored["at"], before)
        self.assertEqual(stored["receipt"], "")  # No receipt yet; a later one ends the quiet period.
        for contract, session in (("not a contract", "s"), (CONTRACT, ""), (CONTRACT, "a\nb")):
            with self.subTest(contract=contract, session=session):
                with self.assertRaises(ValueError):
                    gate.mark_review_pending(self.root, contract, session)

    def test_a_change_after_marking_blocks_again(self):
        for provider, session in self.adapters():
            gate.mark_review_pending(self.root, CONTRACT, session)
            self.assert_released(self.stop(provider, session))
            (self.root / "work.txt").write_text(f"changed while {provider} review ran\n")
            self.assert_blocked(self.stop(provider, session))
            self.assertFalse(self.marker.exists(), "a changed state ends the quiet period")
            (self.root / "work.txt").write_text("change\n")
            self.assert_blocked(self.stop(provider, session, active=True))

    def test_another_contract_or_session_is_not_quieted(self):
        for provider, session in self.adapters():
            self.touch()
            gate.mark_review_pending(self.root, OTHER, session)
            self.assert_blocked(self.stop(provider, session))
            self.touch()
            gate.mark_review_pending(self.root, CONTRACT, "someone-else")
            self.assert_blocked(self.stop(provider, session))

    def test_an_expired_or_future_marker_blocks(self):
        for provider, session in self.adapters():
            for offset in (-gate.PENDING_LIMIT - 60, 3600):
                self.touch()
                gate.mark_review_pending(self.root, CONTRACT, session)
                stored = json.loads(self.marker.read_text())
                stored["at"] += offset
                self.marker.write_text(json.dumps(stored))
                self.assert_blocked(self.stop(provider, session))

    def test_a_failing_check_still_blocks(self):
        for provider, session in self.adapters():
            gate.mark_review_pending(self.root, CONTRACT, session)
            self.flag.unlink()
            try:
                self.assert_blocked(self.stop(provider, session), text="quality gate failed")
            finally:
                self.flag.write_text("")

    def test_control_drift_still_blocks(self):
        for provider, session in self.adapters():
            (self.root / ".claude/settings.json").write_text(json.dumps({"drift": provider}))
            gate.mark_review_pending(self.root, CONTRACT, session)  # The marker covers the drifted state.
            self.assert_blocked(self.stop(provider, session), text="protected")

    def test_a_recorded_receipt_ends_the_quiet_period(self):
        for provider, session in self.adapters():
            gate.mark_review_pending(self.root, CONTRACT, session)
            self.assert_released(self.stop(provider, session))
            self.record("REWORK")
            self.assert_blocked(self.stop(provider, session), text="rework")
            self.record("PASS")
            passed = self.stop(provider, session)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertNotIn("pending", passed.stdout)
            self.assertFalse(self.marker.exists(), "a pass ends the quiet period")
            self.touch()

    def test_a_high_risk_floor_is_quieted_only_for_its_marked_contract(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## High-risk areas\n\n- `secure/`: fixture boundary.\n")
        self.assertEqual(lean(self.root, "gate", "accept-controls", "--reason", "fixture areas").returncode, 0)
        (self.root / "secure").mkdir()
        (self.root / "secure/rule.txt").write_text("deny\n")
        low = "Contract: risk=LOW quality=STANDARD acceptance=fixture"
        for provider in ("claude", "codex"):
            with self.subTest(adapter=provider):
                session = f"{provider}-low"
                self.bind(session, low)
                self.assert_blocked(self.stop(provider, session), text="high-risk areas changed")
                self.touch()
                gate.mark_review_pending(self.root, OTHER, session)
                self.assert_blocked(self.stop(provider, session), text="high-risk areas changed")
                self.touch()
                gate.mark_review_pending(self.root, low, session)
                self.assert_released(self.stop(provider, session))


if __name__ == "__main__":
    unittest.main()
