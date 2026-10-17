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


def stop_refusal(result):
    """Claude's Stop adapter refuses with a JSON decision block on exit 0; read it as exit 2 + reason."""
    try:
        data = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("decision") == "block":
        return subprocess.CompletedProcess(result.args, 2, "", result.stderr + data["reason"])
    return result


class GateIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean integrity ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py", ".lean/scripts/gate_mode.py", ".lean/scripts/contract_guard.py",
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

    def configured_stop(self, payload=None):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        return stop_refusal(subprocess.run(["bash", "-c", command], input=json.dumps(payload or {}),
                                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
                                           text=True, capture_output=True))

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
        self.assertFalse((self.root / ".claude/.gate-cache").exists())
        (self.root / "code.txt").unlink()
        result = self.configured_stop()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(counter.read_text().splitlines(), ["run"] * 3)

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
        result = subprocess.run(["bash", str(self.root / ".claude/hooks/session-start.sh")],
                                env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
                                text=True, capture_output=True)
        self.assertIn("Quality Gate undefined", result.stdout)


class TrustedControlRefTests(unittest.TestCase):
    """Protected controls that equal a trusted remote-tracking ref are accepted without a manual step."""
    TRUSTED = "<!-- trusted-control-refs: refs/remotes/origin/develop refs/remotes/origin/main -->\n"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean trusted refs ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
                     ".lean/scripts/gate_mode.py", ".lean/scripts/contract_guard.py", ".claude/hooks/quality-gate.sh",
                     ".claude/hooks/session-start.sh", ".codex/hooks.json", ".codex/hooks/quality_gate.py", ".gitignore"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
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

    def claude(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        env.pop("CLAUDE_GATE_FORCE", None)
        return stop_refusal(subprocess.run(["bash", str(self.root / ".claude/hooks/quality-gate.sh")],
                                           input="{}", text=True, capture_output=True, env=env))

    def codex(self):
        return subprocess.run(["python3", str(self.root / ".codex/hooks/quality_gate.py"), "run", "--root", str(self.root)],
                              input="{}", text=True, capture_output=True)

    def history(self):
        return json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())["history"]

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

    def test_executable_bit_and_extra_hooks_must_match(self):
        self.upstream()
        hook = self.root / ".claude/hooks/session-start.sh"
        hook.chmod(0o644)
        self.assertEqual(self.claude().returncode, 2)
        hook.chmod(0o755)
        extra = self.root / ".claude/hooks/extra.sh"
        extra.write_text("#!/bin/sh\n")
        self.assertEqual(self.claude().returncode, 2)
        extra.unlink()
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


if __name__ == "__main__":
    unittest.main()
