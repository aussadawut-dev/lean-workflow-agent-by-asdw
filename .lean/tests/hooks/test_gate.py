"""Gate failures, provenance and review evidence in disposable Git repositories."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean, stop_refusal  # noqa: E402

CONTRACT = "Contract: risk=HIGH quality=HIGH acceptance=fixture checks pass"
DECLARE = "python3 .lean/bin/lean contract declare --contract '{}'"


def environment(root):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    env.pop("LEAN_GATE_FORCE", None)
    env.pop("LEAN_GATE_LOCK_FD", None)
    return env


class GateIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean integrity ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        self.project = self.root / ".lean/PROJECT.md"
        self.project.write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / ".claude/settings.json").write_text('{}')
        self.git("init", "-q")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", ".")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "init")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def gate(self, *args, payload=None):
        args = ["--hook" if arg == "--claude-hook" else arg for arg in args]
        return lean(self.root, "gate", "run", *args, input=json.dumps(payload or {}), env=environment(self.root))

    def evidence(self, *args):
        if args[0] == "record-review" and "--state" not in args:
            snapshot = self.evidence("state")
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            args = (*args, "--state", snapshot.stdout.strip())
        return lean(self.root, "evidence", *args)

    def configured_stop(self, payload=None):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        return stop_refusal(subprocess.run(["bash", "-c", command], input=json.dumps(payload or {}),
                                           env=environment(self.root), text=True, capture_output=True))

    def test_configured_stop_reuses_pass_but_rechecks_changes_and_failures(self):
        command = "printf 'run\\n' >> .agent-runtime/check-runs; test ! -f code.txt"
        self.project.write_text(self.project.read_text().replace("true", command))
        for _ in range(2):
            result = self.configured_stop()
            self.assertEqual(result.returncode, 0, result.stderr)
        counter = self.root / ".agent-runtime/check-runs"
        self.assertEqual(counter.read_text().splitlines(), ["run"])
        (self.root / "code.txt").write_text("changed input\n")
        result = self.configured_stop()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.root / ".agent-runtime/gate-cache").exists())
        (self.root / "code.txt").unlink()
        result = self.configured_stop()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(counter.read_text().splitlines(), ["run"] * 3)

    def test_an_earlier_receipt_for_the_same_state_still_counts(self):
        # TCK021/TCK022: a second contract's receipt on the same state replaced the first one.
        first, second = CONTRACT, CONTRACT + " second"
        for contract in (first, second):
            self.assertEqual(self.evidence("record-review", "--contract", contract, "--reviewer", "independent-test",
                                           "--evidence", "fixture", "--verdict", "PASS").returncode, 0)
        for contract in (first, second):
            with self.subTest(contract=contract):
                checked = self.evidence("check-review", "--contract", contract)
                self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.gate("--contract", first, "--require-review").returncode, 0)
        rework = CONTRACT + " third"
        for verdict in ("PASS", "REWORK"):  # A later REWORK for the same contract wins over its earlier PASS.
            self.evidence("record-review", "--contract", rework, "--reviewer", "independent-test",
                          "--evidence", "fixture", "--verdict", verdict)
        self.assertNotEqual(self.evidence("check-review", "--contract", rework).returncode, 0)
        (self.root / "code.txt").write_text("changed\n")  # A changed state needs a new review for every contract.
        self.assertNotEqual(self.evidence("check-review", "--contract", first).returncode, 0)

    def test_configured_stop_cache_still_checks_current_contract_and_review(self):
        self.assertEqual(self.configured_stop().returncode, 0)
        path = self.transcript([self.user("high task"), self.assistant(CONTRACT)])
        result = self.configured_stop({"transcript_path": path})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("review", result.stderr.lower())
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT,
                                      "--reviewer", "independent-test", "--evidence", "fixture",
                                      "--verdict", "PASS").returncode, 0)
        self.assertEqual(self.configured_stop({"transcript_path": path}).returncode, 0)
        path = self.transcript([self.user("different high task"), self.assistant(CONTRACT + " again")])
        result = self.configured_stop({"transcript_path": path})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("review", result.stderr.lower())

    def transcript(self, entries):
        path = self.root / ".agent-runtime/transcript.jsonl"
        path.parent.mkdir(exist_ok=True)
        path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
        return str(path)

    def assistant(self, text):
        return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}

    def user(self, text):
        return {"type": "user", "message": {"content": text}}

    def test_continued_stops_that_keep_changing_release_unverified_after_three(self):
        self.project.write_text(self.project.read_text().replace("true", "false"))
        self.evidence("accept-controls", "--reason", "Fixture selects a failing gate")
        for index in range(3):
            (self.root / "attempt.txt").write_text(f"attempt {index}\n")
            result = self.gate("--claude-hook", payload={"stop_hook_active": index > 0})
            self.assertEqual(result.returncode, 2, result.stderr)
        (self.root / "attempt.txt").write_text("attempt 3\n")
        released = self.gate("--claude-hook", payload={"stop_hook_active": True})
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertIn("UNVERIFIED", json.loads(released.stdout)["systemMessage"])
        self.assertTrue((self.root / ".agent-runtime/gate-failed").exists())
        self.assertFalse((self.root / ".agent-runtime/gate-cache").exists())
        (self.root / "attempt.txt").write_text("attempt 4\n")
        fresh = self.gate("--claude-hook", payload={"stop_hook_active": False})
        self.assertEqual(fresh.returncode, 2, fresh.stderr)

    def test_an_unchanged_refusal_blocks_once_then_only_warns(self):
        # The agent has already seen this refusal; blocking every Stop while it waits on the user loops.
        self.project.write_text(self.project.read_text().replace("true", "false"))
        self.evidence("accept-controls", "--reason", "Fixture selects a failing gate")
        first = self.gate("--claude-hook", payload={"stop_hook_active": False, "session_id": "s"})
        self.assertEqual(first.returncode, 2, first.stderr)
        for active in (True, False):
            with self.subTest(stop_hook_active=active):
                repeated = self.gate("--claude-hook", payload={"stop_hook_active": active, "session_id": "s"})
                self.assertEqual(repeated.returncode, 0, repeated.stderr)
                self.assertIn("UNVERIFIED", json.loads(repeated.stdout)["systemMessage"])
                self.assertTrue((self.root / ".agent-runtime/gate-failed").exists())
                self.assertFalse((self.root / ".agent-runtime/gate-cache").exists())
        (self.root / "changed.txt").write_text("new work\n")
        changed = self.gate("--claude-hook", payload={"stop_hook_active": False, "session_id": "s"})
        self.assertEqual(changed.returncode, 2, changed.stderr)

    def test_a_new_refusal_reason_blocks_even_when_the_state_is_unchanged(self):
        # Accepting drift changes no Git-visible byte, but the failing check is news to the agent.
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        self.project.write_text(self.project.read_text().replace("true", "echo CHECK-FAILED; false"))
        drift = self.gate("--claude-hook", payload={"session_id": "s"})
        self.assertEqual(drift.returncode, 2, drift.stderr)
        self.assertIn("protected", drift.stderr.lower())
        self.evidence("accept-controls", "--reason", "User approved fixture gate change")
        failing = self.gate("--claude-hook", payload={"stop_hook_active": True, "session_id": "s"})
        self.assertEqual(failing.returncode, 2, failing.stderr)
        self.assertIn("CHECK-FAILED", failing.stderr)

    def test_another_session_is_shown_a_refusal_it_has_not_seen(self):
        self.project.write_text(self.project.read_text().replace("true", "false"))
        self.evidence("accept-controls", "--reason", "Fixture selects a failing gate")
        self.assertEqual(self.gate("--claude-hook", payload={"session_id": "one"}).returncode, 2)
        self.assertEqual(self.gate("--claude-hook", payload={"session_id": "one"}).returncode, 0)
        other = self.gate("--claude-hook", payload={"session_id": "two"})
        self.assertEqual(other.returncode, 2, other.stderr)

    def test_an_unchanged_control_drift_refusal_blocks_once(self):
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        self.project.write_text(self.project.read_text().replace("true", "echo changed"))
        self.assertEqual(self.gate("--claude-hook", payload={"session_id": "s"}).returncode, 2)
        repeated = self.gate("--claude-hook", payload={"stop_hook_active": True, "session_id": "s"})
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertIn("UNVERIFIED", json.loads(repeated.stdout)["systemMessage"])
        # Accepting the drift lets the gate run its checks, which pass and clear the refusal.
        self.evidence("accept-controls", "--reason", "User approved fixture gate change")
        self.assertEqual(self.gate("--claude-hook", payload={"session_id": "s"}).returncode, 0)
        self.assertFalse((self.root / ".agent-runtime/gate-failed").exists())

    def test_empty_gate_and_missing_project_are_explicitly_unconfigured(self):
        self.project.write_text("<!-- gate:start -->\n```sh\n```\n<!-- gate:end -->\n")
        result = self.gate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("undefined", result.stderr.lower())
        self.project.unlink()
        result = self.gate()
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_default_reruns_after_ignored_environment_changes(self):
        self.project.write_text(self.project.read_text().replace("true", "test ! -f .env"))
        self.assertEqual(self.gate("--claude-hook").returncode, 0)
        (self.root / ".env").write_text("environment changed\n")
        result = self.gate("--claude-hook")
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_old_contract_and_tool_input_do_not_satisfy_current_turn(self):
        for current in (self.assistant("DONE"), {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"new_string": CONTRACT}}]}}):
            path = self.transcript([self.user("old task"), self.assistant(CONTRACT),
                                    self.user("new task"), current])
            result = self.gate("--claude-hook", payload={"transcript_path": path})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Contract", result.stderr)

    def test_contract_must_be_first_line_and_precede_known_write(self):
        for entries in ([self.assistant("Here is a quote:\n" + CONTRACT)],
                        [{"type": "assistant", "message": {"content": [
                            {"type": "tool_use", "name": "Write", "input": {}}]}}, self.assistant(CONTRACT)]):
            path = self.transcript([self.user("task"), *entries])
            result = self.gate("--claude-hook", payload={"transcript_path": path})
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_contract_in_second_text_block_is_not_the_reply_first_line(self):
        low = "Contract: risk=LOW quality=STANDARD acceptance=fixture checks pass"
        path = self.transcript([self.user("task"), {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Introductory prose"}, {"type": "text", "text": low}]}}])
        result = self.gate("--claude-hook", payload={"transcript_path": path})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Contract", result.stderr)

    def test_high_review_is_required_and_bound_to_current_bytes_and_modes_not_staging(self):
        path = self.transcript([self.user("task"), self.assistant(CONTRACT)])
        result = self.gate("--claude-hook", payload={"transcript_path": path})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("review", result.stderr.lower())
        (self.root / "code.txt").write_text("reviewed\n")
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                       "--evidence", "Fixture reviewed", "--verdict", "PASS").returncode, 0)
        self.assertEqual(self.gate("--claude-hook", payload={"transcript_path": path}).returncode, 0)
        os.chmod(self.root / "code.txt", 0o755)
        self.assertNotEqual(self.gate("--require-review", "--contract", CONTRACT).returncode, 0)
        os.chmod(self.root / "code.txt", 0o644)
        # Staging the reviewed bytes changes no content, so the receipt still covers what ships.
        self.git("add", "code.txt")
        self.assertEqual(self.gate("--require-review", "--contract", CONTRACT).returncode, 0)

    def commit(self, message):
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", message)

    def record_pass(self):
        result = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                               "--evidence", "fixture", "--verdict", "PASS")
        self.assertEqual(result.returncode, 0, result.stderr)

    def covered(self):
        return self.evidence("check-review", "--contract", CONTRACT).returncode == 0

    def test_receipt_survives_staging_committing_and_tracker_bookkeeping(self):
        tracking = self.root / "docs/tracking"
        tracking.mkdir(parents=True)
        (tracking / "TCK001.md").write_text("Status: REVIEWING\n")
        (self.root / "old.txt").write_text("retired\n")
        self.git("add", ".")
        self.commit("base")
        (self.root / "code.txt").write_text("reviewed\n")
        (self.root / "old.txt").unlink()
        self.record_pass()
        self.git("add", "-A")
        self.assertTrue(self.covered(), "staging the reviewed change")
        self.commit("reviewed change")
        self.assertTrue(self.covered(), "committing the reviewed change")
        (tracking / "TCK001.md").write_text("Status: DONE\nEvidence: review PASS\n")
        (tracking / "TCK002.md").write_text("Status: PLANNED\n")
        self.assertTrue(self.covered(), "tracker records written after review")
        self.git("add", "-A")
        self.commit("close tracker")
        self.assertTrue(self.covered(), "committing tracker records")

    def test_receipt_rejects_any_unreviewed_content_change(self):
        (self.root / "base.txt").write_text("base\n")
        (self.root / "moved.txt").write_text("moved\n")
        self.git("add", ".")
        self.commit("base")
        (self.root / "base.txt").write_text("reviewed\n")
        self.record_pass()

        def write(name, text):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        changes = {
            "other Markdown": lambda: write("docs/guide.md", "new\n"),
            "nested tracking file": lambda: write("docs/tracking/notes/TCK009.md", "x\n"),
            "non-Markdown tracking file": lambda: write("docs/tracking/data.json", "{}\n"),
            "deletion": lambda: (self.root / "moved.txt").unlink(),
            "rename": lambda: (self.root / "moved.txt").rename(self.root / "renamed.txt"),
            "gate control": lambda: (self.root / ".claude/settings.json").write_text('{"changed": true}'),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                self.assertTrue(self.covered())
                change()
                self.assertFalse(self.covered(), name)
                self.git("checkout", "-q", "HEAD", "--", ".")
                shutil.rmtree(self.root / "docs", ignore_errors=True)
                (self.root / "renamed.txt").unlink(missing_ok=True)
                (self.root / "base.txt").write_text("reviewed\n")

    def test_receipt_rejects_staged_content_that_differs_from_the_reviewed_bytes(self):
        # Committing would ship the staged bytes, which nobody reviewed.
        (self.root / "base.txt").write_text("base\n")
        self.git("add", ".")
        self.commit("base")
        (self.root / "base.txt").write_text("reviewed\n")
        self.record_pass()
        (self.root / "base.txt").write_text("unreviewed\n")
        self.git("add", "base.txt")
        (self.root / "base.txt").write_text("reviewed\n")
        self.assertFalse(self.covered())

    def reviewed_pair(self):
        """Commit a.txt and b.txt, then review a change to both."""
        for name in ("a.txt", "b.txt"):
            (self.root / name).write_text("base\n")
        self.git("add", ".")
        self.commit("base")
        for name in ("a.txt", "b.txt"):
            (self.root / name).write_text("reviewed\n")
        self.record_pass()

    def test_receipt_rejects_committed_bytes_that_were_never_reviewed(self):
        # Committing unreviewed bytes and restoring the reviewed ones leaves the tree unchanged.
        self.reviewed_pair()
        (self.root / "a.txt").write_text("unreviewed\n")
        self.git("add", "-A")
        self.commit("unreviewed")
        (self.root / "a.txt").write_text("reviewed\n")
        self.assertFalse(self.covered())

    def test_receipt_rejects_a_staged_deletion_of_a_file_still_on_disk(self):
        self.reviewed_pair()
        self.git("rm", "-q", "--cached", "b.txt")
        self.assertFalse(self.covered(), "staged deletion")
        self.commit("drop b")
        self.assertFalse(self.covered(), "committed deletion")

    def test_receipt_rejects_a_partial_commit_of_the_reviewed_change(self):
        # The commit would ship a.txt without b.txt, a combination nobody reviewed.
        self.reviewed_pair()
        self.git("add", "a.txt")
        self.commit("only a")
        self.assertFalse(self.covered(), "partial commit")
        self.git("add", "b.txt")
        self.commit("rest")
        self.assertTrue(self.covered(), "the whole reviewed change is committed")

    def test_commit_during_review_cannot_be_recorded_as_reviewed(self):
        # The captured state must bind HEAD: a commit between capture and record ships unseen bytes.
        self.reviewed_pair()
        captured = self.evidence("state").stdout.strip()
        (self.root / "a.txt").write_text("unreviewed\n")
        self.git("add", "-A")
        self.commit("during review")
        (self.root / "a.txt").write_text("reviewed\n")
        recorded = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                 "--evidence", "fixture", "--verdict", "PASS", "--state", captured)
        self.assertNotEqual(recorded.returncode, 0)
        self.assertFalse(self.covered())

    def test_committed_mode_change_is_caught_without_core_filemode(self):
        self.reviewed_pair()
        self.git("config", "core.fileMode", "false")
        self.git("update-index", "--chmod=+x", "a.txt")
        self.assertFalse(self.covered(), "staged mode change")
        self.git("add", "b.txt")
        self.commit("mode")
        self.assertFalse(self.covered(), "committed mode change")

    def test_receipt_without_a_reviewed_base_is_refused(self):
        self.record_pass()
        path = self.root / ".agent-runtime/review.json"
        receipt = json.loads(path.read_text())
        receipt.pop("base", None)
        path.write_text(json.dumps(receipt))
        self.assertFalse(self.covered())

    def test_gate_state_still_changes_with_commits_and_trackers(self):
        # The gate cache must rerun checks that read history or tracker records.
        tracking = self.root / "docs/tracking"
        tracking.mkdir(parents=True)
        (tracking / "TCK001.md").write_text("Status: PLANNED\n")
        before = self.evidence("gate-state").stdout.strip()
        self.assertTrue(before)
        (tracking / "TCK001.md").write_text("Status: DONE\n")
        tracker_edit = self.evidence("gate-state").stdout.strip()
        self.assertNotEqual(tracker_edit, before)
        self.git("add", "-A")
        self.commit("tracker")
        self.assertNotEqual(self.evidence("gate-state").stdout.strip(), tracker_edit)

    def test_review_cannot_be_reused_for_another_contract_or_a_rework(self):
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "test-reviewer",
                                       "--evidence", "fixture", "--verdict", "REWORK").returncode, 0)
        self.assertNotEqual(self.evidence("check-review", "--contract", CONTRACT).returncode, 0)
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "test-reviewer",
                                       "--evidence", "fixture", "--verdict", "PASS").returncode, 0)
        self.assertNotEqual(self.evidence("check-review", "--contract", CONTRACT + " again").returncode, 0)
        self.assertEqual(self.evidence("check-review", "--contract", CONTRACT).returncode, 0)
        (self.root / "new.txt").write_text("later work")
        self.assertNotEqual(self.evidence("check-review", "--contract", CONTRACT).returncode, 0)

    def test_protected_gate_drift_requires_explicit_recorded_acceptance(self):
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        self.project.write_text(self.project.read_text().replace("true", "echo changed"))
        result = self.gate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("protected", result.stderr.lower())
        accepted = self.evidence("accept-controls", "--reason", "User approved fixture gate change")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.gate().returncode, 0)
        settings = self.root / ".claude/settings.json"
        settings.write_text('{"changed":true}')
        self.assertEqual(self.gate().returncode, 2)

    def bind(self, session, contract):
        """Declare `contract` for `session` the way the PreToolUse guard binds it."""
        bound = lean(self.root, "hook", "claude", "pre-tool",
                     input=json.dumps({"session_id": session, "tool_name": "Bash",
                                       "tool_input": {"command": DECLARE.format(contract)}}))
        self.assertEqual(bound.returncode, 0, bound.stderr)

    def test_protected_gate_drift_is_accepted_by_an_independent_high_review(self):
        # The manual accept-controls step stalled unattended runs after every reviewed hook or gate
        # edit; a HIGH-depth PASS receipt for the session contract, whose state binds the changed
        # controls, accepts them instead.
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        self.project.write_text(self.project.read_text().replace("true", "echo changed"))
        self.bind("s", CONTRACT)  # The runner reads the session's declared contract itself.
        refused = self.gate("--session", "s")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("protected", refused.stderr.lower())
        self.assertIn("PASS review", refused.stderr)
        recorded = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                 "--evidence", "fixture", "--verdict", "PASS")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        accepted = self.gate("--session", "s")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn("independent HIGH-depth PASS review by independent-test", accepted.stderr)
        record = json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())
        self.assertTrue(record["history"][-1]["reason"].startswith(
            "automatic: independent HIGH-depth review PASS by independent-test for " + CONTRACT))
        self.assertEqual(record["history"][-1]["after"], record["controls"])
        # A further control change is news again: the receipt no longer covers the state.
        (self.root / ".claude/settings.json").write_text('{"changed":true}')
        again = self.gate("--session", "s")
        self.assertEqual(again.returncode, 2, again.stderr)
        self.assertIn("protected", again.stderr.lower())

    def test_other_receipts_and_a_missing_session_contract_do_not_accept_drift(self):
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        stale = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                              "--evidence", "fixture", "--verdict", "PASS")  # Recorded before the drift.
        self.assertEqual(stale.returncode, 0, stale.stderr)
        self.project.write_text(self.project.read_text().replace("true", "echo changed"))
        low = "Contract: risk=LOW quality=STANDARD acceptance=fixture"
        other = "Contract: risk=HIGH quality=HIGH acceptance=some other task"
        self.bind("s", CONTRACT)
        self.bind("low", low)
        cases = (("stale", None, None, ("--session", "s")),
                 ("rework", "REWORK", CONTRACT, ("--session", "s")),
                 ("low depth", "PASS", low, ("--session", "low")),
                 ("another HIGH contract", "PASS", other, ("--session", "s")),
                 # Review round 3: a valid receipt, but the contract came from the command line or a session
                 # that declared nothing; only the guard's store names a contract the author cannot record for.
                 ("explicit contract only", "PASS", CONTRACT, ("--contract", CONTRACT)),
                 ("free-text session contract", None, None, ("--session-contract", CONTRACT)),
                 ("session that declared nothing", None, None, ("--session", "nobody")),
                 ("no session", None, None, ()))
        for label, verdict, contract, gate_args in cases:
            with self.subTest(receipt=label):
                if verdict:
                    recorded = self.evidence("record-review", "--contract", contract, "--reviewer", "independent-test",
                                             "--evidence", "fixture", "--verdict", verdict)
                    self.assertEqual(recorded.returncode, 0, recorded.stderr)
                result = self.gate(*gate_args)
                self.assertEqual(result.returncode, 2, (label, result.stderr))
                if label != "free-text session contract":  # An unknown option is refused before any check.
                    self.assertIn("protected", result.stderr.lower())
                history = json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())["history"]
                self.assertFalse(any(entry["reason"].startswith("automatic") for entry in history))

    def test_a_control_change_committed_before_the_review_is_not_accepted_by_it(self):
        # Review round 1: a reviewer sees the diff against HEAD, so a control change already in HEAD
        # when the review began was never in front of them; the reviewed base must still hold the
        # accepted controls.
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        (self.root / ".claude/settings.json").write_text('{"committed":true}')
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qam", "control change")
        (self.root / "notes.txt").write_text("unrelated work\n")
        recorded = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                 "--evidence", "notes only", "--verdict", "PASS")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.bind("s", CONTRACT)
        result = self.gate("--session", "s")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("protected", result.stderr.lower())
        self.assertEqual(self.evidence("accept-controls", "--reason", "User approved the committed control change").returncode, 0)
        self.assertEqual(self.gate("--session", "s").returncode, 0)

    def test_a_committed_control_change_edited_again_is_not_accepted_by_a_review_of_the_edit(self):
        # Review of the new contract, round 1: the reviewer's diff starts at the committed value, so a
        # review of a later edit must not accept the committed change underneath it.
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        settings = self.root / ".claude/settings.json"
        settings.write_text('{"hooks":"committed"}')
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qam", "control change")
        settings.write_text('{"hooks":"committed","x":1}')
        recorded = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                 "--evidence", "edit only", "--verdict", "PASS")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.bind("s", CONTRACT)
        result = self.gate("--session", "s")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("protected", result.stderr.lower())

    def test_a_control_git_does_not_show_is_not_accepted_by_review(self):
        # An ignored control never appears in the reviewed diff, although the receipt state binds its bytes.
        gitignore = self.root / ".gitignore"
        gitignore.write_text(gitignore.read_text() + ".lean/gate.json\n")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qam", "ignore gate mode")
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        self.assertEqual(self.gate().returncode, 0)  # Record the baseline with the ignore in place.
        (self.root / ".lean/gate.json").write_text('{"auto": true}\n')
        (self.root / "notes.txt").write_text("unrelated work\n")
        recorded = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                 "--evidence", "notes only", "--verdict", "PASS")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.bind("s", CONTRACT)
        result = self.gate("--session", "s")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("protected", result.stderr.lower())

    def test_receipt_mismatch_names_what_differs(self):
        # A reviewer that paraphrased the contract can re-record in one step when told the exact text.
        paraphrase = "Contract: risk=HIGH quality=HIGH acceptance=fixture check passes"
        self.assertEqual(self.evidence("record-review", "--contract", paraphrase, "--reviewer", "independent-test",
                                       "--evidence", "fixture", "--verdict", "PASS").returncode, 0)
        result = self.evidence("check-review", "--contract", CONTRACT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(CONTRACT, result.stderr)
        self.assertIn(paraphrase, result.stderr)
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                       "--evidence", "fixture", "--verdict", "PASS").returncode, 0)
        (self.root / "later.txt").write_text("change after review")
        changed = self.evidence("check-review", "--contract", CONTRACT)
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("shipping state changed", changed.stderr)

    def test_control_drift_refusal_also_names_pending_high_risk_review(self):
        # One refusal names both steps, so the agent can ask once instead of learning them a Stop at a time.
        self.project.write_text(self.project.read_text() + "\n## High-risk areas\n\n- `secure/`: fixture boundary.\n")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qam", "areas")
        self.assertEqual(self.gate("--claude-hook", "--seed").returncode, 0)
        (self.root / "secure").mkdir()
        (self.root / "secure/rule.txt").write_text("deny\n")
        self.project.write_text(self.project.read_text().replace("true", "echo changed"))
        result = self.gate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("protected", result.stderr.lower())
        self.assertIn("HIGH independent review", result.stderr)
        self.assertIn("secure/rule.txt", result.stderr)

    def test_malformed_transcript_fails_with_diagnostic(self):
        path = Path(self.transcript([]))
        path.write_text("not json\n")
        result = self.gate("--claude-hook", payload={"transcript_path": str(path)})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("transcript", result.stderr.lower())

    def test_seed_never_blesses_an_opt_in_cache(self):
        self.project.write_text(self.project.read_text().replace("true", "false"))
        self.assertEqual(self.gate("--claude-hook", "--seed", "--cache-tree").returncode, 0)
        self.assertEqual(self.gate("--claude-hook", "--cache-tree").returncode, 2)

    def test_opt_in_cache_cannot_bypass_high_review(self):
        self.assertEqual(self.gate("--claude-hook", "--cache-tree").returncode, 0)
        path = self.transcript([self.user("high task"), self.assistant(CONTRACT)])
        result = self.gate("--claude-hook", "--cache-tree", payload={"transcript_path": path})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("review", result.stderr.lower())

    def test_review_depth_uses_fields_not_acceptance_or_trivial_reason(self):
        for contract in ("Contract: risk=LOW quality=STANDARD acceptance=prints risk=HIGH quality=VERY_HIGH",
                         "Contract: trivial (documentation of risk=HIGH quality=VERY_HIGH)"):
            with self.subTest(contract=contract):
                path = self.transcript([self.user("task"), self.assistant(contract)])
                result = self.gate("--claude-hook", payload={"transcript_path": path})
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_reviewed_shipping_state_meets_the_high_risk_floor_for_a_later_contract(self):
        self.project.write_text(self.project.read_text() + "\n## High-risk areas\n\n- `secure/`: fixture boundary.\n")
        (self.root / "secure").mkdir()
        (self.root / "secure/rule.txt").write_text("deny\n")
        status = "Contract: trivial (status report)"
        refused = self.gate("--contract", status)
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("High-risk areas changed", refused.stderr)
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                       "--evidence", "fixture", "--verdict", "PASS").returncode, 0)
        # The reviewed state is what ships, so a later status-only contract needs no new review...
        for contract in (status, "Contract: risk=LOW quality=STANDARD acceptance=answer only"):
            result = self.gate("--contract", contract)
            self.assertEqual(result.returncode, 0, result.stderr)
        path = self.transcript([self.user("how far along?"), self.assistant(status)])
        hooked = self.gate("--claude-hook", payload={"transcript_path": path})
        self.assertEqual(hooked.returncode, 0, hooked.stderr)
        # ...but a HIGH contract still needs a receipt for itself, and any further change needs review.
        other_high = "Contract: risk=HIGH quality=HIGH acceptance=another reviewed change"
        self.assertEqual(self.gate("--contract", other_high).returncode, 2)
        (self.root / "secure/rule.txt").write_text("allow\n")
        changed = self.gate("--contract", status)
        self.assertEqual(changed.returncode, 2, changed.stderr)
        self.assertIn("High-risk areas changed", changed.stderr)
        self.assertEqual(self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "independent-test",
                                       "--evidence", "fixture", "--verdict", "REWORK").returncode, 0)
        (self.root / "secure/rule.txt").write_text("deny\n")
        self.assertEqual(self.gate("--contract", status).returncode, 2)  # The latest receipt is not a PASS.
        # Review round 1: a PASS under a lower contract (say, written by mistake or by the author)
        # does not stand in for the review a High-risk change needs.
        self.assertEqual(self.evidence("record-review", "--contract", "Contract: risk=LOW quality=STANDARD acceptance=y",
                                       "--reviewer", "r", "--evidence", "e", "--verdict", "PASS").returncode, 0)
        low = self.gate("--contract", status)
        self.assertEqual(low.returncode, 2, low.stderr)

    def test_very_high_quality_requires_review_at_low_or_medium_risk(self):
        for risk in ("LOW", "MEDIUM"):
            contract = f"Contract: risk={risk} quality=VERY_HIGH acceptance=fixture checks pass"
            path = self.transcript([self.user("task"), self.assistant(contract)])
            result = self.gate("--claude-hook", payload={"transcript_path": path})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("review", result.stderr.lower())

    def test_review_receipt_refuses_changes_since_review_started(self):
        before = self.evidence("state").stdout.strip()
        (self.root / "late.txt").write_text("unseen change")
        result = self.evidence("record-review", "--contract", CONTRACT, "--reviewer", "test",
                               "--evidence", "fixture", "--verdict", "PASS", "--state", before)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / ".agent-runtime/review.json").exists())

    def test_malformed_gate_markers_never_run_commands(self):
        for text in ("<!-- gate:start -->\ntrue\n", "<!-- gate:end -->\n<!-- gate:start -->\ntrue\n",
                     "<!-- gate:start -->\ntrue\n<!-- gate:end -->\n<!-- gate:end -->\n"):
            self.project.write_text(text)
            self.evidence("accept-controls", "--reason", "Fixture selects malformed input")
            result = self.gate()
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_default_session_warning_for_undefined_gate(self):
        self.project.write_text("<!-- gate:start -->\n```sh\n```\n<!-- gate:end -->\n")
        result = lean(self.root, "hook", "claude", "session-start", input="", env=environment(self.root))
        self.assertIn("Quality Gate undefined", result.stdout)


class TrustedControlRefTests(unittest.TestCase):
    """Protected controls that equal a trusted remote-tracking ref are accepted without a manual step."""
    TRUSTED = "<!-- trusted-control-refs: refs/remotes/origin/develop refs/remotes/origin/main -->\n"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean trusted refs ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        self.project = self.root / ".lean/PROJECT.md"
        self.project.write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n" + self.TRUSTED)
        self.settings = self.root / ".claude/settings.json"
        self.settings.write_text("{}")
        self.git("init", "-q")
        self.commit("init")
        self.assertEqual(self.claude().returncode, 0)  # First use records the baseline.

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                               *args], check=True, text=True, capture_output=True).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def upstream(self, ref="refs/remotes/origin/develop"):
        """Simulate a fetched upstream ref whose tree is the current commit."""
        self.git("update-ref", ref, "HEAD")

    def claude(self, payload=None):
        return stop_refusal(lean(self.root, "hook", "claude", "stop", input=json.dumps(payload or {}),
                                 env=environment(self.root)))

    def codex(self, *args):
        return lean(self.root, "gate", "run", *args, input="{}", env=environment(self.root))

    def codex_event(self, event, session):
        return stop_refusal(lean(self.root, "hook", "codex", event, input=json.dumps({"session_id": session}),
                                 env=environment(self.root)))

    def history(self):
        return json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())["history"]

    def test_manual_codex_streams_progress_without_success_output(self):
        import select
        self.project.write_text(self.project.read_text().replace("true", "echo hidden-check-output; while [ ! -f .agent-runtime/release ]; do sleep 0.05; done"))
        self.commit("slow check")
        self.upstream()
        process = subprocess.Popen([sys.executable, str(self.root / ".lean/bin/lean"), "--root", str(self.root),
                                    "gate", "run"], cwd=self.root, env=environment(self.root),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import time
            deadline = time.monotonic() + 5
            progress = b""
            while b"Quality Gate: check 1 started" not in progress and time.monotonic() < deadline:
                ready, _, _ = select.select([process.stderr], [], [], max(0, deadline - time.monotonic()))
                if not ready:
                    break
                chunk = os.read(process.stderr.fileno(), 4096)
                if not chunk:
                    break
                progress += chunk
            self.assertIn(b"Quality Gate: check 1 started", progress,
                          "progress must arrive while the check is still running")
            self.assertIsNone(process.poll())
            self.assertEqual(lean(self.root, "gate", "status").stdout.strip(), "RUNNING")
        finally:
            (self.root / ".agent-runtime/release").touch()
            out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, err)
        self.assertNotIn("hidden-check-output", out + err)
        self.assertIn("Quality Gate: check 1 passed", err)

    def test_reviewed_control_drift_is_accepted_for_both_providers(self):
        helper = [sys.executable, str(self.root / ".lean/bin/lean"), "--root", str(self.root), "evidence"]

        def bind(session, contract):  # Declare the contract for the session, as the PreToolUse guard does.
            bound = lean(self.root, "hook", "claude", "pre-tool",
                         input=json.dumps({"session_id": session, "tool_name": "Bash",
                                           "tool_input": {"command": DECLARE.format(contract)}}))
            self.assertEqual(bound.returncode, 0, bound.stderr)

        def record(contract):
            snapshot = subprocess.run(helper + ["state"], text=True, capture_output=True).stdout.strip()
            recorded = subprocess.run(helper + ["record-review", "--contract", contract, "--reviewer", "independent-test",
                                                "--evidence", "fixture", "--verdict", "PASS", "--state", snapshot],
                                      text=True, capture_output=True)
            self.assertEqual(recorded.returncode, 0, recorded.stderr)

        runs = {"claude": lambda: self.claude({"session_id": "claude-s"}),
                "codex": lambda: self.codex_event("stop", "codex-s")}
        for name, run in runs.items():
            with self.subTest(adapter=name):
                self.settings.write_text(json.dumps({"reviewed": name}))  # No trusted ref carries this.
                bind(f"{name}-s", CONTRACT)
                refused = run()
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertIn("protected", refused.stderr.lower())
                record(CONTRACT)
                if name == "codex":  # An explicit run trusts no contract for this: the author may have passed it.
                    explicit = self.codex("--contract", CONTRACT)
                    self.assertEqual(explicit.returncode, 2, explicit.stderr)
                result = run()
                self.assertEqual(result.returncode, 0, result.stderr)
                if name == "claude":  # A passing Codex Stop reports a JSON message, not the runner's notes.
                    self.assertIn("independent HIGH-depth PASS review", result.stderr)
                self.assertTrue(self.history()[-1]["reason"].startswith(
                    "automatic: independent HIGH-depth review PASS by independent-test"))
                self.assertEqual(run().returncode, 0)
                self.commit(f"accepted {name} controls")  # The next diff starts at the accepted value.
        # Review round 2: a Codex Stop whose session declared nothing falls back to the receipt's own
        # contract for its review check; that contract must not accept drift, or an author could record
        # a PASS under a made-up HIGH contract and have the gate call it an independent review.
        self.settings.write_text(json.dumps({"reviewed": "fabricated"}))
        record("Contract: risk=HIGH quality=HIGH acceptance=fabricated")
        self.assertEqual(self.codex_event("session-start", "fresh").returncode, 0)
        fresh = self.codex_event("stop", "fresh")
        self.assertEqual(fresh.returncode, 2, fresh.stderr)
        self.assertIn("protected", fresh.stderr.lower())
        self.assertFalse(any("fabricated" in entry["reason"] for entry in self.history()))

    def test_controls_matching_a_trusted_remote_ref_are_accepted_for_both_providers(self):
        for adapter in (self.claude, self.codex):
            with self.subTest(adapter=adapter.__name__):
                self.settings.write_text(json.dumps({"from": adapter.__name__}))
                self.commit("upstream controls")
                self.upstream()
                result = adapter()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("match refs/remotes/origin/develop", result.stderr)
                self.assertTrue(self.history()[-1]["reason"].startswith("automatic: controls match trusted ref"))
                self.assertEqual(adapter().returncode, 0)

    def test_a_later_listed_ref_matches_after_an_unresolvable_one(self):
        self.settings.write_text('{"main": true}')
        self.commit("release")
        blob = self.git("rev-parse", "HEAD:.claude/settings.json")
        self.git("update-ref", "refs/remotes/origin/develop", blob)  # Exists, but is not a commit.
        self.upstream("refs/remotes/origin/main")
        result = self.claude()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("match refs/remotes/origin/main", result.stderr)

    def test_a_local_tag_is_not_trusted(self):
        self.project.write_text(self.project.read_text().replace("refs/remotes/origin/main", "refs/tags/v1"))
        self.commit("list a tag")
        self.git("tag", "v1")
        result = self.claude()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("accepts only refs/remotes/*", result.stderr)

    def test_replace_objects_cannot_make_a_trusted_ref_match_local_edits(self):
        self.upstream()
        trusted = self.git("rev-parse", "refs/remotes/origin/develop:.claude/settings.json")
        self.settings.write_text('{"local": true}')
        local = self.git("hash-object", "-w", str(self.settings))
        self.git("replace", trusted, local)
        self.assertEqual(self.claude().returncode, 2)

    def test_local_drift_from_every_trusted_ref_still_blocks_for_both_providers(self):
        self.upstream()
        self.settings.write_text('{"local": true}')
        for adapter in (self.claude, self.codex):
            with self.subTest(adapter=adapter.__name__):
                result = adapter()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("No trusted-control-refs entry matches", result.stderr)
        self.assertEqual(self.history(), [])

    def test_a_local_commit_without_a_trusted_ref_blocks(self):
        self.settings.write_text('{"committed": true}')
        self.commit("local only")
        self.git("branch", "develop")  # refs/heads/develop is not a trusted ref.
        self.assertEqual(self.claude().returncode, 2)

    def test_executable_bit_and_gate_code_must_match(self):
        self.upstream()
        entry = self.root / ".lean/bin/lean"
        entry.chmod(0o644)
        self.assertEqual(self.claude().returncode, 2)
        entry.chmod(0o755)
        module = self.root / ".lean/lean/gate.py"
        original = module.read_text()
        module.write_text(original + "\n# local edit\n")
        self.assertEqual(self.claude().returncode, 2)
        module.write_text(original)
        self.assertEqual(self.claude().returncode, 0)

    def test_local_branch_head_or_commit_ids_are_rejected_as_trusted_refs(self):
        for value in ("refs/heads/develop", "refs/tags/v1", "HEAD", self.git("rev-parse", "HEAD"), "refs/remotes/../heads/x"):
            with self.subTest(value=value):
                self.project.write_text(self.project.read_text().replace(self.TRUSTED, "")
                                        + f"<!-- trusted-control-refs: {value} -->\n")
                self.TRUSTED = f"<!-- trusted-control-refs: {value} -->\n"
                result = self.claude()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("accepts only refs/remotes/*", result.stderr)

    def test_adding_a_trusted_ref_is_itself_a_protected_change(self):
        self.upstream()
        self.project.write_text(self.project.read_text().replace("refs/remotes/origin/main", "refs/remotes/origin/main refs/remotes/evil/x"))
        self.assertEqual(self.claude().returncode, 2)

    def test_without_trusted_refs_drift_still_needs_manual_acceptance(self):
        self.project.write_text(self.project.read_text().replace(self.TRUSTED, ""))
        self.commit("drop trusted refs")
        self.upstream()
        result = self.claude()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("trusted-control-refs", result.stderr)


class PassReuseTests(unittest.TestCase):
    """A pass recorded with --cache-tree, direct or Stop, is reused by either provider's Stop on that state."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean pass reuse ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        # Every check run appends to an ignored file, and an ignored flag decides pass or fail, so
        # neither counting runs nor failing a check changes the shipping state.
        self.runs = self.root / ".agent-runtime/check-runs"
        self.flag = self.root / ".agent-runtime/pass"
        (self.root / ".lean/PROJECT.md").write_text(
            "<!-- gate:start -->\n```sh\nprintf 'run\\n' >> .agent-runtime/check-runs; test -f .agent-runtime/pass\n"
            "```\n<!-- gate:end -->\n")
        (self.root / ".claude/settings.json").write_text("{}")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.flag.parent.mkdir(exist_ok=True)
        self.flag.write_text("")
        self.assertEqual(self.direct().returncode, 0)  # First use records the gate controls.
        (self.root / "work.txt").write_text("change\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                               *args], check=True, text=True, capture_output=True).stdout.strip()

    def count(self):
        return self.runs.read_text().count("run\n") if self.runs.exists() else 0

    def direct(self, *args):
        return lean(self.root, "gate", "run", *args, env=environment(self.root))

    def claude_stop(self, payload=None):
        """The Stop command exactly as the shipped Claude settings configure it."""
        command = json.loads((ROOT / ".claude/settings.json").read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
        return stop_refusal(subprocess.run(["bash", "-c", command], input=json.dumps(payload or {}), text=True,
                                           capture_output=True, env=environment(self.root)))

    def codex_stop(self, payload=None):
        """The Stop command exactly as the shipped Codex hooks configure it, run inside the checkout."""
        command = json.loads((ROOT / ".codex/hooks.json").read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
        return stop_refusal(subprocess.run(["bash", "-c", command], cwd=self.root, input=json.dumps(payload or {}),
                                           text=True, capture_output=True, env=environment(self.root)))

    def test_a_direct_pass_is_reused_by_both_providers_stops(self):
        for name, stop in (("claude", self.claude_stop), ("codex", self.codex_stop)):
            with self.subTest(adapter=name):
                (self.root / "work.txt").write_text(f"change for {name}\n")
                before = self.count()
                self.assertEqual(self.direct("--cache-tree").returncode, 0)
                self.assertEqual(self.count(), before + 1)
                result = stop()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.count(), before + 1, "the Stop reran checks a direct run had passed")
                (self.root / "work.txt").write_text(f"changed again for {name}\n")
                self.assertEqual(stop().returncode, 0)
                self.assertEqual(self.count(), before + 2, "a changed state must run the checks again")

    def test_one_providers_stop_pass_is_reused_by_the_other(self):
        for first, second in ((self.claude_stop, self.codex_stop), (self.codex_stop, self.claude_stop)):
            with self.subTest(first=first.__name__):
                (self.root / "work.txt").write_text(f"change before {first.__name__}\n")
                before = self.count()
                self.assertEqual(first().returncode, 0)
                self.assertEqual(second().returncode, 0)
                self.assertEqual(self.count(), before + 1)

    def test_runs_without_the_opt_in_always_execute(self):
        self.assertEqual(self.direct("--cache-tree").returncode, 0)
        before = self.count()
        self.assertEqual(self.direct().returncode, 0)
        explicit = lean(self.root, "gate", "run", input="{}", env=environment(self.root))
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        # A project that drops --cache-tree from its Codex Stop command gets a full run, as with Claude.
        plain = stop_refusal(lean(self.root, "hook", "codex", "stop", input="{}", env=environment(self.root)))
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
        self.assertEqual(self.count(), before + 3)

    def test_a_failing_run_drops_the_recorded_pass(self):
        self.assertEqual(self.direct("--cache-tree").returncode, 0)
        cache = self.root / ".agent-runtime/gate-cache"
        self.assertTrue(cache.is_file())
        self.flag.unlink()  # The check now fails although the shipping state is unchanged.
        self.assertEqual(self.direct().returncode, 2)
        self.assertFalse(cache.exists())
        for name, stop in (("claude", self.claude_stop), ("codex", self.codex_stop)):
            with self.subTest(adapter=name):
                self.assertEqual(stop().returncode, 2, "a Stop reused a pass after the same state failed")

    def transcript(self, text):
        """A Claude transcript whose current reply opens with `text`, kept out of the shipping state."""
        self.transcripts = getattr(self, "transcripts", 0) + 1
        path = self.root / f".agent-runtime/transcript-{self.transcripts}.jsonl"
        path.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}) + "\n")
        return {"transcript_path": str(path), "stop_hook_active": False}

    def test_a_direct_pass_does_not_excuse_a_missing_contract_line(self):
        # A direct run never reads the transcript, so its pass may skip the commands but not the
        # Claude Stop's contract check, which backs up the guard for writes it did not catch.
        self.assertEqual(self.direct("--cache-tree").returncode, 0)
        result = self.claude_stop(self.transcript("Done."))
        self.assertEqual(result.returncode, 2, "a direct pass excused changed work with no contract line")

    def test_a_stop_that_settles_the_contract_keeps_the_pass_for_follow_ups(self):
        self.assertEqual(self.direct("--cache-tree").returncode, 0)
        before = self.count()
        settled = self.claude_stop(self.transcript("Contract: risk=LOW quality=STANDARD acceptance=checks pass"))
        self.assertEqual(settled.returncode, 0, settled.stdout + settled.stderr)
        self.assertEqual(self.count(), before, "the Stop reran checks a direct run had passed")
        follow_up = self.claude_stop(self.transcript("Here is the answer."))
        self.assertEqual(follow_up.returncode, 0, "a chat-only turn on a settled state needs no new contract")

    def test_a_direct_run_cannot_record_a_pass_over_an_unreviewed_high_risk_change(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## High-risk areas\n\n- `secure/`: auth boundary.\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "areas")
        (self.root / "secure").mkdir()
        (self.root / "secure/auth.py").write_text("x = 1\n")
        result = self.direct("--cache-tree")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("High-risk", result.stderr)
        self.assertFalse((self.root / ".agent-runtime/gate-cache").exists())

    def test_a_reused_pass_still_requires_the_high_review(self):
        for name, stop in (("claude", self.claude_stop), ("codex", self.codex_stop)):
            with self.subTest(adapter=name):
                session = f"{name}-high"
                bound = lean(self.root, "hook", "claude", "pre-tool",
                             input=json.dumps({"session_id": session, "tool_name": "Bash",
                                               "tool_input": {"command": DECLARE.format(CONTRACT)}}))
                self.assertEqual(bound.returncode, 0, bound.stderr)
                self.assertEqual(self.direct("--cache-tree").returncode, 0)
                before = self.count()
                result = stop({"session_id": session})
                self.assertEqual(result.returncode, 2, "a recorded pass let a HIGH contract skip its review receipt")
                self.assertEqual(self.count(), before)


class GateProgressTests(unittest.TestCase):
    """Direct runs number each check with its elapsed time; Stops run quietly so a refusal stays the same."""

    git, direct, claude_stop, codex_stop, transcript = (PassReuseTests.git, PassReuseTests.direct,
                                                         PassReuseTests.claude_stop, PassReuseTests.codex_stop,
                                                         PassReuseTests.transcript)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean gate progress ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        # Ignored flags slow the first check and fail the second without changing the shipping state.
        self.slow = self.root / ".agent-runtime/slow"
        self.flag = self.root / ".agent-runtime/pass"
        (self.root / ".lean/PROJECT.md").write_text(
            "<!-- gate:start -->\n```sh\nif [ -f .agent-runtime/slow ]; then sleep 2.2; fi\n"
            "test -f .agent-runtime/pass\n```\n<!-- gate:end -->\n")
        (self.root / ".claude/settings.json").write_text("{}")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.flag.parent.mkdir(exist_ok=True)
        self.flag.write_text("")
        self.first = self.direct()  # First use records the gate controls.
        self.assertEqual(self.first.returncode, 0, self.first.stderr)
        (self.root / "work.txt").write_text("change\n")

    def test_a_direct_run_numbers_each_check_with_its_elapsed_time(self):
        for line in ("Quality Gate: check 1 started", "Quality Gate: check 1 passed (",
                     "Quality Gate: check 2 started", "Quality Gate: check 2 passed ("):
            self.assertIn(line, self.first.stderr)
        quiet = self.direct("--quiet")
        self.assertEqual(quiet.returncode, 0, quiet.stderr)
        self.assertNotIn("Quality Gate: check", quiet.stderr)

    def test_a_claude_stop_refusal_carries_only_the_failure(self):
        self.flag.unlink()
        result = self.claude_stop(self.transcript("Contract: risk=LOW quality=STANDARD acceptance=checks pass"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("test -f .agent-runtime/pass", result.stderr)
        self.assertNotIn("Quality Gate: check", result.stderr)

    def test_a_codex_stop_refusal_is_unchanged_when_only_check_times_differ(self):
        declare = DECLARE.format("Contract: risk=LOW quality=STANDARD acceptance=checks pass")
        bound = lean(self.root, "hook", "codex", "pre-tool",
                     input=json.dumps({"session_id": "codex", "tool_name": "Bash", "tool_input": {"command": declare}}))
        self.assertEqual(bound.returncode, 0, bound.stderr)
        self.flag.unlink()
        first = self.codex_stop({"session_id": "codex", "stop_hook_active": False})
        self.assertEqual(first.returncode, 2, first.stdout + first.stderr)
        self.assertNotIn("Quality Gate: check", first.stderr)
        self.slow.write_text("")  # The passing check now takes over two seconds; nothing else changes.
        again = self.codex_stop({"session_id": "codex", "stop_hook_active": True})
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("refused again with nothing changed", again.stdout)


if __name__ == "__main__":
    unittest.main()
