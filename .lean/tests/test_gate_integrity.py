"""Gate failures, provenance and review evidence in disposable Git repositories."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = "Contract: risk=HIGH quality=HIGH acceptance=fixture checks pass"


class GateIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean integrity ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py",
                     ".claude/hooks/quality-gate.sh", ".claude/hooks/session-start.sh", ".gitignore"):
            source = ROOT / name
            if source.exists():
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, path)
        self.project = self.root / ".lean/PROJECT.md"
        self.project.write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / ".claude/settings.json").write_text('{}')
        self.git("init", "-q")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "add", ".")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "init")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def gate(self, *args, payload=None):
        return subprocess.run(["bash", str(self.root / ".lean/scripts/quality-gate.sh"),
                               "--root", str(self.root), *args], input=json.dumps(payload or {}),
                              text=True, capture_output=True)

    def evidence(self, *args):
        if args[0] == "record-review" and "--state" not in args:
            snapshot = self.evidence("state")
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            args = (*args, "--state", snapshot.stdout.strip())
        return subprocess.run(["python3", str(self.root / ".lean/scripts/gate_evidence.py"),
                               "--root", str(self.root), *args], text=True, capture_output=True)

    def transcript(self, entries):
        path = self.root / ".agent-runtime/transcript.jsonl"
        path.parent.mkdir(exist_ok=True)
        path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
        return str(path)

    def assistant(self, text):
        return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}

    def user(self, text):
        return {"type": "user", "message": {"content": text}}

    def test_continued_stops_release_unverified_without_success(self):
        self.project.write_text(self.project.read_text().replace("true", "false"))
        for index in range(3):
            result = self.gate("--claude-hook", payload={"stop_hook_active": index > 0})
            self.assertEqual(result.returncode, 2, result.stderr)
        released = self.gate("--claude-hook", payload={"stop_hook_active": True})
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertIn("UNVERIFIED", json.loads(released.stdout)["systemMessage"])
        self.assertTrue((self.root / ".claude/.gate-failed").exists())
        self.assertFalse((self.root / ".claude/.gate-cache").exists())
        fresh = self.gate("--claude-hook", payload={"stop_hook_active": False})
        self.assertEqual(fresh.returncode, 2, fresh.stderr)

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

    def test_high_review_is_required_and_bound_to_current_bytes_modes_and_index(self):
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
        self.git("add", "code.txt")
        self.assertNotEqual(self.gate("--require-review", "--contract", CONTRACT).returncode, 0)

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
        result = subprocess.run(["bash", str(self.root / ".claude/hooks/session-start.sh")],
                                env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
                                text=True, capture_output=True)
        self.assertIn("Quality Gate undefined", result.stdout)


if __name__ == "__main__":
    unittest.main()
