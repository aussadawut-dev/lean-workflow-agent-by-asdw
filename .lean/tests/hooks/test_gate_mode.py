"""Shared gate policy, CLI and provider adapters in disposable workspaces."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean  # noqa: E402


def environment(root, force=False):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    env.pop("LEAN_GATE_FORCE", None)
    env.pop("LEAN_GATE_LOCK_FD", None)
    if force:
        env["LEAN_GATE_FORCE"] = "1"
    return env


class GateModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean gate mode ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)
        (self.root / ".gitignore").unlink()  # The 4.x fixture had no ignore file outside Git cases.
        self.config = self.root / ".lean/gate.json"
        self.project = self.root / ".lean/PROJECT.md"
        self.project.write_text("<!-- gate:start -->\n```sh\nprintf ran >> gate-runs\n```\n<!-- gate:end -->\n")
        self.marker = self.root / "gate-runs"

    def mode(self, *args):
        return lean(self.root, "gate", "mode", *args, env=environment(self.root))

    def auto(self, value):
        self.config.write_text(json.dumps({"auto": value}))

    def codex(self, event="stop", payload=None, extra=()):
        """The Codex hook for an event, or (`run`) an explicit gate run as Codex performs it."""
        stdin = json.dumps({} if payload is None else payload)
        if event == "run":
            return lean(self.root, "gate", "run", *extra, input=stdin, env=environment(self.root))
        return lean(self.root, "hook", "codex", event, *extra, input=stdin, env=environment(self.root))

    @staticmethod
    def refusal(result):
        """Exit 2 with a message, or (Claude's Stop adapter) a JSON decision block on exit 0."""
        if result.returncode == 0 and result.stdout.strip():
            output = json.loads(result.stdout)
            if output.get("decision") == "block":
                return output["reason"]
        return result.stderr if result.returncode == 2 else None

    def claude(self, *args, force=False):
        return lean(self.root, "hook", "claude", "stop", *args, input="{}", env=environment(self.root, force))

    def test_missing_config_is_read_only_auto_default(self):
        result = self.mode()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"mode": "auto", "configured": False})
        self.assertFalse(self.config.exists())
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertEqual(self.claude().returncode, 0)
        self.assertEqual(self.marker.read_text(), "ran")

    def test_cli_round_trip_and_invalid_arguments_preserve_policy(self):
        expected = {
            "manual": {"auto": False},
            "auto": {"auto": True},
            "auto_fixloop": {"auto": True, "fixloop": True},
            "manual_fixloop": {"auto": False, "fixloop": True},
        }
        for mode, payload in expected.items():
            self.assertEqual(self.mode(mode).returncode, 0)
            self.assertEqual(json.loads(self.config.read_text()), payload)
            self.assertEqual(json.loads(self.mode().stdout), {"mode": mode, "configured": True})
        self.config.write_text(json.dumps({"auto": True, "fixloop": False}))
        self.assertEqual(json.loads(self.mode().stdout), {"mode": "auto", "configured": True})
        original = self.config.read_bytes()
        for args in (("bad",), ("manual", "extra"), ("auto_fixloop", "--policy"), ("manual_fixloop", "--check-auto")):
            self.assertEqual(self.mode(*args).returncode, 2)
            self.assertEqual(self.config.read_bytes(), original)

    def test_setting_a_mode_is_logged_and_asks_for_a_commit(self):
        # asdw-harness: sessions found an untracked .lean/gate.json nobody could trace.
        env = dict(environment(self.root), LEAN_SESSION_ID="session-a")
        self.auto(True)
        result = lean(self.root, "gate", "mode", "manual_fixloop", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"mode": "manual_fixloop", "configured": True})
        self.assertIn("commit .lean/gate.json", result.stderr)
        events = [json.loads(line) for line in (self.root / ".agent-runtime/activity.jsonl").read_text().splitlines()]
        logged = [event for event in events if event["event"] == "gate-mode"]
        self.assertEqual([(event["before"], event["after"], event["session"]) for event in logged],
                         [("auto", "manual_fixloop", "session-a")])
        self.assertNotIn("commit", self.mode().stderr)  # Reading the mode logs and asks nothing.

    def test_manual_and_manual_fixloop_stops_never_run_or_claim_pass(self):
        for mode in ("manual", "manual_fixloop"):
            self.assertEqual(self.mode(mode).returncode, 0)
            for result in (self.codex(), self.claude()):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("NOT_RUN", result.stdout + result.stderr)
                self.assertNotIn("checks passed", result.stdout + result.stderr)
                if mode == "manual_fixloop":
                    self.assertIn("auto-loop", result.stdout + result.stderr)
                    self.assertIn("user authorization", result.stdout + result.stderr)
            self.assertFalse(self.marker.exists())
            self.assertFalse((self.root / ".agent-runtime/gate-controls.json").exists())

    def test_codex_session_start_announces_policy_without_checks(self):
        for mode, auto_flag in (("manual", False), ("auto", True), ("auto_fixloop", True), ("manual_fixloop", False)):
            self.assertEqual(self.mode(mode).returncode, 0)
            result = self.codex("session-start")
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn(f"auto={str(auto_flag).lower()}", context)
            if mode.endswith("_fixloop"):
                self.assertIn(f"mode={mode}", context)
                self.assertIn("auto-loop", context)
            self.assertFalse(self.marker.exists())

    def test_claude_session_start_preserves_quiet_auto_and_announces_manual_and_fixloop(self):
        (self.root / ".lean/config.json").write_text('{"mode":"standard","configured":true}')
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        def session_start():
            return lean(self.root, "hook", "claude", "session-start", input="", env=environment(self.root))
        auto = session_start()
        self.assertEqual(auto.returncode, 0, auto.stderr)
        self.assertEqual(auto.stdout, "")
        self.auto(False)
        manual = session_start()
        self.assertEqual(manual.returncode, 0, manual.stderr)
        self.assertIn("NOT_RUN", manual.stdout)
        for mode in ("auto_fixloop", "manual_fixloop"):
            self.assertEqual(self.mode(mode).returncode, 0)
            out = session_start()
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn(f"mode={mode}", out.stdout)
            self.assertIn("auto-loop", out.stdout)
        self.assertFalse(self.marker.exists())

    def test_auto_fixloop_runs_checks_and_emits_fixloop_failure_guidance(self):
        self.assertEqual(self.mode("auto_fixloop").returncode, 0)
        self.assertEqual(self.claude().returncode, 0)
        self.assertEqual(self.codex().returncode, 0)
        self.assertEqual(self.marker.read_text(), "ranran")
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        self.assertEqual(lean(self.root, "gate", "accept-controls", "--reason", "Fixture selects failing gate").returncode, 0)
        claude_fail = self.claude()
        self.assertIn("Fixloop mode is active", self.refusal(claude_fail) or "")
        codex_fail = json.loads(self.codex().stdout)
        self.assertEqual(codex_fail["decision"], "block")
        self.assertIn("fixloop active", codex_fail["reason"])
        self.assertIn("Fixloop mode is active", codex_fail["reason"])

    def test_codex_auto_stop_uses_default_and_runs_checks(self):
        result = self.codex()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checks passed", json.loads(result.stdout)["systemMessage"])
        self.assertEqual(self.marker.read_text(), "ran")

    def test_manual_explicit_runs_both_providers_and_direct_runner(self):
        self.auto(False)
        self.assertEqual(self.codex("run").returncode, 0)
        self.assertEqual(self.claude(force=True).returncode, 0)
        direct = lean(self.root, "gate", "run", env=environment(self.root))
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual(self.marker.read_text(), "ranranran")

    def test_explicit_run_honours_contract_and_review_flags(self):
        contract = "Contract: risk=HIGH quality=HIGH acceptance=review matches"
        result = self.codex("run", extra=("--contract", contract, "--require-review"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("review", result.stderr.lower())

    def test_invalid_policy_blocks_cli_and_explicit_runs(self):
        for text in ('{"auto":"false"}', '{"auto":0}', '{"auto":true,"fixloop":"yes"}', '{"auto":true,"extra":1}',
                     '{"fixloop":true}', '[]', '{}', '{bad', '{"auto":true,"auto":false}'):
            self.config.write_text(text)
            for result in (self.mode(), self.mode("manual"), self.codex("run")):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("NOT_RUN", result.stdout + result.stderr)
            for result in (self.claude(), self.claude(force=True)):
                self.assertIn("NOT_RUN", self.refusal(result) or "", result.stdout + result.stderr)
            output = json.loads(self.codex().stdout)
            self.assertIn("NOT_RUN", output["systemMessage"])
            self.assertFalse(self.marker.exists())
            self.assertEqual(self.config.read_text(), text)

    def test_policy_symlink_is_not_followed(self):
        outside = self.root / "outside.json"
        outside.write_text('{"auto":true}')
        self.config.symlink_to(outside)
        self.assertEqual(self.mode("manual").returncode, 2)
        self.assertEqual(self.codex("run").returncode, 2)
        refused = self.claude()
        self.assertEqual(refused.returncode, 0, refused.stderr)
        self.assertTrue(self.refusal(refused))
        self.assertEqual(outside.read_text(), '{"auto":true}')

    def test_invalid_codex_input_never_runs_checks(self):
        for payload in ([], {"stop_hook_active": "true"}):
            output = json.loads(self.codex(payload=payload).stdout)
            self.assertIn("NOT_RUN", output["systemMessage"])
            self.assertFalse(self.marker.exists())

    def test_failure_never_turns_into_a_pass_on_continuation(self):
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        for index in range(3):
            attempt = json.loads(self.codex(payload={"stop_hook_active": index > 0}).stdout)
            self.assertEqual(attempt["decision"], "block")
        continued = json.loads(self.codex(payload={"stop_hook_active": True}).stdout)
        self.assertIn("UNVERIFIED", continued["systemMessage"])
        self.assertNotIn("decision", continued)
        self.assertEqual(self.codex("run").returncode, 2)

    def test_an_unwritable_codex_refusal_marker_releases_continued_stops(self):
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        (self.root / ".agent-runtime/codex-gate-failed").mkdir(parents=True)  # Cannot be read or written.
        self.assertEqual(json.loads(self.codex(payload={"stop_hook_active": False}).stdout)["decision"], "block")
        continued = json.loads(self.codex(payload={"stop_hook_active": True}).stdout)
        self.assertNotIn("decision", continued)
        self.assertIn("UNVERIFIED", continued["systemMessage"])

    def test_a_symlinked_codex_runtime_releases_continued_stops(self):
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        elsewhere = Path(outside.name)
        shutil.rmtree(self.root / ".agent-runtime", ignore_errors=True)
        (self.root / ".agent-runtime").symlink_to(elsewhere)
        self.assertEqual(json.loads(self.codex(payload={"stop_hook_active": False}).stdout)["decision"], "block")
        continued = json.loads(self.codex(payload={"stop_hook_active": True}).stdout)
        self.assertNotIn("decision", continued)
        self.assertIn("UNVERIFIED", continued["systemMessage"])
        self.assertEqual(list(elsewhere.iterdir()), [], "nothing is written through the link")

    def test_clearing_codex_markers_removes_each_one_independently(self):
        from lean import hooks
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        (runtime / "codex-gate-failed").mkdir()  # Cannot be unlinked.
        (runtime / "codex-gate-refusal").write_text("fingerprint")
        hooks.clear_codex_refusals(self.root)
        self.assertFalse((runtime / "codex-gate-refusal").exists())

    def test_a_new_session_clears_each_codex_marker_independently(self):
        from lean import hooks
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        (runtime / "codex-gate-refusal").mkdir()  # Cannot be unlinked.
        (runtime / "codex-gate-failed").write_text("c2")
        hooks.clear_codex_session_refusals(self.root)
        self.assertFalse((runtime / "codex-gate-failed").exists())

    def test_a_planted_codex_marker_link_is_never_followed(self):
        # Ported from a downstream project's local patch: the markers were written through symlinks.
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        victim = Path(outside.name) / "victim.txt"
        victim.write_text("keep me")
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        for name in ("codex-gate-failed", "codex-gate-refusal"):
            (runtime / name).unlink(missing_ok=True)
            (runtime / name).symlink_to(victim)
        self.assertEqual(json.loads(self.codex(payload={"stop_hook_active": False}).stdout)["decision"], "block")
        continued = json.loads(self.codex(payload={"stop_hook_active": True}).stdout)
        self.assertNotIn("decision", continued)
        self.assertIn("UNVERIFIED", continued["systemMessage"])
        self.assertEqual(victim.read_text(), "keep me", "a marker was written through a planted link")

    def test_codex_unchanged_refusal_blocks_once_then_releases_unverified_until_change(self):
        (self.root / ".gitignore").write_text(".agent-runtime/\ngate-runs\n")
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        first = json.loads(self.codex(payload={"stop_hook_active": False, "session_id": "s1"}).stdout)
        self.assertEqual(first["decision"], "block")
        repeated = json.loads(self.codex(payload={"stop_hook_active": True, "session_id": "s1"}).stdout)
        self.assertIn("UNVERIFIED", repeated["systemMessage"])
        self.assertNotIn("decision", repeated)
        (self.root / "work.txt").write_text("changed\n")
        after_change = json.loads(self.codex(payload={"stop_hook_active": True, "session_id": "s1"}).stdout)
        self.assertEqual(after_change["decision"], "block")

    def test_shared_lock_blocks_all_explicit_entrypoints(self):
        self.auto(False)
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        with (runtime / "quality-gate.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for result in (self.codex("run"), self.claude(force=True)):
                self.assertIn("busy", self.refusal(result) or "", result.stdout + result.stderr)
            self.assertFalse(self.marker.exists())

    def test_auto_stop_reuses_only_current_review_for_high_risk_changes(self):
        (self.root / ".gitignore").write_text(".agent-runtime/\ngate-runs\n")
        self.project.write_text(self.project.read_text() + "\n## High-risk areas\n\n- `critical/`: fixture boundary.\n")
        critical = self.root / "critical/source.py"
        critical.parent.mkdir()
        critical.write_text("value = 1\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        self.assertEqual(self.codex("run").returncode, 0)
        critical.write_text("value = 2\n")
        contract = "Contract: risk=HIGH quality=HIGH acceptance=fixture reviewed"
        state = lean(self.root, "evidence", "state").stdout.strip()
        recorded = lean(self.root, "evidence", "record-review", "--contract", contract, "--reviewer",
                        "fixture-independent", "--verdict", "PASS", "--state", state, "--evidence",
                        "fixture shipping diff reviewed")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        output = json.loads(self.codex().stdout)
        self.assertIn("checks passed", output["systemMessage"])
        critical.write_text("value = 3\n")
        output = json.loads(self.codex().stdout)
        self.assertEqual(output["decision"], "block")
        self.assertIn("review", output["reason"].lower())

    def test_mode_and_codex_controls_drift_are_guarded(self):
        self.assertEqual(self.codex("run").returncode, 0)
        self.assertEqual(self.mode("manual").returncode, 0)
        result = self.codex("run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Protected gate controls changed", result.stderr)
        self.assertEqual(self.marker.read_text(), "ran")

    def test_registered_codex_commands_run_from_a_checkout_with_spaces(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        hooks = json.loads((self.root / ".codex/hooks.json").read_text())["hooks"]
        for event in ("SessionStart", "Stop"):
            command = hooks[event][0]["hooks"][0]["command"]
            result = subprocess.run(["bash", "-c", command], cwd=self.root,
                                    input="{}", text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsInstance(json.loads(result.stdout), dict)
        self.assertEqual(self.marker.read_text(), "ran")

    def test_symlinked_runtime_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / ".agent-runtime").symlink_to(outside)
        self.assertEqual(self.mode("manual").returncode, 2)
        self.assertFalse(self.config.exists())
