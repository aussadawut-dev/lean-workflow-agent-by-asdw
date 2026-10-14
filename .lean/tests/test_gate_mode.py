"""Shared gate policy, CLI and provider adapters in disposable workspaces."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GateModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean gate mode ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (".lean/scripts/gate_mode.py", ".codex/hooks/quality_gate.py", ".codex/hooks.json",
                     ".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py", ".lean/scripts/gate_lock.py",
                     ".claude/hooks/quality-gate.sh", ".claude/hooks/session-start.sh"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.config = self.root / ".codex/quality-gate.json"
        self.project = self.root / ".lean/PROJECT.md"
        self.project.write_text("<!-- gate:start -->\n```sh\nprintf ran >> gate-runs\n```\n<!-- gate:end -->\n")
        self.marker = self.root / "gate-runs"

    def mode(self, *args):
        return subprocess.run(["python3", str(self.root / ".lean/scripts/gate_mode.py"), *args],
                              capture_output=True, text=True)

    def auto(self, value):
        self.config.write_text(json.dumps({"auto": value}))

    def codex(self, event="stop", payload=None, extra=()):
        return subprocess.run(["python3", str(self.root / ".codex/hooks/quality_gate.py"), event, *extra],
                              input=json.dumps({} if payload is None else payload), text=True, capture_output=True)

    def claude(self, *args, force=False):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        env.pop("CLAUDE_GATE_FORCE", None)
        if force:
            env["CLAUDE_GATE_FORCE"] = "1"
        return subprocess.run(["bash", str(self.root / ".claude/hooks/quality-gate.sh"), *args],
                              input="{}", text=True, capture_output=True, env=env)

    def test_missing_config_is_read_only_auto_default(self):
        result = self.mode()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"mode": "auto", "configured": False})
        self.assertFalse(self.config.exists())
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertEqual(self.claude().returncode, 0)
        self.assertEqual(self.marker.read_text(), "ran")

    def test_cli_round_trip_and_invalid_arguments_preserve_policy(self):
        for mode in ("manual", "auto"):
            self.assertEqual(self.mode(mode).returncode, 0)
            self.assertEqual(json.loads(self.config.read_text()), {"auto": mode == "auto"})
            self.assertEqual(json.loads(self.mode().stdout), {"mode": mode, "configured": True})
        original = self.config.read_bytes()
        for args in (("bad",), ("manual", "extra")):
            self.assertEqual(self.mode(*args).returncode, 2)
            self.assertEqual(self.config.read_bytes(), original)

    def test_manual_stops_never_run_or_claim_pass(self):
        self.auto(False)
        for result in (self.codex(), self.claude()):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NOT_RUN", result.stdout + result.stderr)
            self.assertNotIn("checks passed", result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertFalse((self.root / ".agent-runtime/gate-controls.json").exists())

    def test_codex_session_start_announces_policy_without_checks(self):
        for auto in (False, True):
            self.auto(auto)
            result = self.codex("session-start")
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn(f"auto={str(auto).lower()}", context)
            self.assertFalse(self.marker.exists())

    def test_claude_session_start_preserves_quiet_auto_and_announces_manual(self):
        (self.root / ".lean/config.json").write_text('{"mode":"standard","configured":true}')
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        script = str(self.root / ".claude/hooks/session-start.sh")
        auto = subprocess.run(["bash", script], text=True, capture_output=True, env=env)
        self.assertEqual(auto.returncode, 0, auto.stderr)
        self.assertEqual(auto.stdout, "")
        self.auto(False)
        manual = subprocess.run(["bash", script], text=True, capture_output=True, env=env)
        self.assertEqual(manual.returncode, 0, manual.stderr)
        self.assertIn("NOT_RUN", manual.stdout)
        self.assertFalse(self.marker.exists())

    def test_codex_auto_stop_uses_default_and_runs_checks(self):
        result = self.codex()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checks passed", json.loads(result.stdout)["systemMessage"])
        self.assertEqual(self.marker.read_text(), "ran")

    def test_manual_explicit_runs_both_providers_and_direct_runner(self):
        self.auto(False)
        self.assertEqual(self.codex("run").returncode, 0)
        self.assertEqual(self.claude(force=True).returncode, 0)
        direct = subprocess.run(["bash", str(self.root / ".lean/scripts/quality-gate.sh"), "--root", str(self.root)],
                                text=True, capture_output=True)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual(self.marker.read_text(), "ranranran")

    def test_codex_run_forwards_contract_and_review_flags(self):
        runner = self.root / ".lean/scripts/quality-gate.sh"
        runner.write_text("printf '%s\\n' \"$@\" > args\n")
        contract = "Contract: risk=HIGH quality=HIGH acceptance=review matches"
        result = self.codex("run", extra=("--contract", contract, "--require-review"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "args").read_text().splitlines(),
                         ["--root", str(self.root.resolve()), "--contract", contract, "--require-review"])

    def test_invalid_policy_blocks_cli_and_explicit_runs(self):
        for text in ('{"auto":"false"}', '{"auto":0}', '[]', '{}', '{bad', '{"auto":true,"auto":false}'):
            self.config.write_text(text)
            for result in (self.mode(), self.mode("manual"), self.codex("run"), self.claude(), self.claude(force=True)):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("NOT_RUN", result.stdout + result.stderr)
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
        self.assertEqual(self.claude().returncode, 2)
        self.assertEqual(outside.read_text(), '{"auto":true}')

    def test_invalid_codex_input_never_runs_checks(self):
        for payload in ([], {"stop_hook_active": "true"}):
            output = json.loads(self.codex(payload=payload).stdout)
            self.assertIn("NOT_RUN", output["systemMessage"])
            self.assertFalse(self.marker.exists())

    def test_failure_never_turns_into_a_pass_on_continuation(self):
        self.project.write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        first = json.loads(self.codex().stdout)
        self.assertEqual(first["decision"], "block")
        continued = json.loads(self.codex(payload={"stop_hook_active": True}).stdout)
        self.assertIn("UNVERIFIED", continued["systemMessage"])
        self.assertNotIn("decision", continued)
        self.assertEqual(self.codex("run").returncode, 2)

    def test_shared_lock_blocks_all_explicit_entrypoints(self):
        self.auto(False)
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        with (runtime / "quality-gate.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for result in (self.codex("run"), self.claude(force=True)):
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("busy", result.stderr)
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
        state = subprocess.check_output(["python3", str(self.root / ".lean/scripts/gate_evidence.py"),
                                         "--root", str(self.root), "state"], text=True).strip()
        recorded = subprocess.run(["python3", str(self.root / ".lean/scripts/gate_evidence.py"), "--root", str(self.root),
                                   "record-review", "--contract", contract, "--reviewer", "fixture-independent",
                                   "--verdict", "PASS", "--state", state, "--evidence", "fixture shipping diff reviewed"],
                                  text=True, capture_output=True)
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

    def test_symlinked_policy_directory_and_runtime_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        config_dir = self.root / ".codex"
        moved = self.root / "saved-codex"
        config_dir.rename(moved)
        config_dir.symlink_to(outside)
        self.assertEqual(self.mode("manual").returncode, 2)
        self.assertFalse((outside / "quality-gate.json").exists())
        config_dir.unlink()
        moved.rename(config_dir)
        (self.root / ".agent-runtime").symlink_to(outside)
        self.assertEqual(self.mode("manual").returncode, 2)
        self.assertFalse(self.config.exists())
