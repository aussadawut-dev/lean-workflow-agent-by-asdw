"""Every workflow module is a gate control, and a broken module never locks the agent out of repairing it."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, install, lean, run_hook  # noqa: E402


class ControlCoverageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")
        first = lean(self.root, "gate", "run")
        self.assertEqual(first.returncode, 0, first.stderr)  # First use records the controls.

    def test_a_change_to_any_workflow_module_is_a_protected_control_change(self):
        modules = sorted((self.root / ".lean/lean").glob("*.py"))
        self.assertIn("hooks.py", [path.name for path in modules])
        for module in modules:
            with self.subTest(module=module.name):
                original = module.read_text()
                module.write_text(original + "\n# local change\n")
                refused = lean(self.root, "gate", "run")
                self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
                self.assertIn("Protected gate controls changed", refused.stderr)
                module.write_text(original)
                self.assertEqual(lean(self.root, "gate", "run").returncode, 0)

    def test_the_impact_map_is_a_control(self):
        path = self.root / ".lean/tests/impact.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"scope": [], "lint_only": [], "rules": []}))
        refused = lean(self.root, "gate", "run")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("Protected gate controls changed", refused.stderr)

    def test_a_review_accepts_controls_whose_names_changed(self):
        # A 4.x baseline names controls that v5 no longer has; a covering HIGH review still accepts it.
        legacy = self.root / ".lean/scripts/quality-gate.sh"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("#!/usr/bin/env bash\n")
        commit(self.root, "4.x control")
        record = self.root / ".agent-runtime/gate-controls.json"
        data = json.loads(record.read_text())
        import hashlib
        data["controls"][".lean/scripts/quality-gate.sh"] = {
            "sha256": hashlib.sha256(legacy.read_bytes()).hexdigest(), "mode": legacy.stat().st_mode & 0o777}
        record.write_text(json.dumps(data))
        legacy.unlink()
        settings = self.root / ".claude/settings.json"
        settings.write_text(settings.read_text().replace("pre-tool", "pre-tool "))
        contract = "Contract: risk=HIGH quality=HIGH acceptance=migration reviewed"
        bound = lean(self.root, "hook", "claude", "pre-tool", input=json.dumps({
            "session_id": "s", "tool_name": "Bash",
            "tool_input": {"command": f"python3 .lean/bin/lean contract declare --contract '{contract}'"}}))
        self.assertEqual(bound.returncode, 0, bound.stderr)
        refused = lean(self.root, "gate", "run", "--session", "s")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        state = lean(self.root, "evidence", "state").stdout.strip()
        recorded = lean(self.root, "evidence", "record-" + "review", "--contract", contract, "--reviewer", "independent",
                        "--evidence", "fixture", "--verdict", "PASS", "--state", state)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        accepted = lean(self.root, "gate", "run", "--session", "s")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn("independent HIGH-depth PASS review", accepted.stderr)

    def test_a_new_workflow_module_is_a_control_change_too(self):
        (self.root / ".lean/lean/extra.py").write_text("x = 1\n")
        refused = lean(self.root, "gate", "run")
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("Protected gate controls changed", refused.stderr)


class BrokenModuleRepairTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tool(self, provider, name, **tool_input):
        return run_hook(self.root, provider, "PreToolUse",
                        {"session_id": "s", "tool_name": name, "tool_input": tool_input})

    def test_a_broken_non_guard_module_does_not_reach_the_guard(self):
        (self.root / ".lean/lean/spawn.py").write_text("def broken(:\n")
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                self.assertEqual(self.tool(provider, "Read", file_path="x.py").returncode, 0)
                denied = self.tool(provider, "Edit", file_path="app.py")
                self.assertEqual(denied.returncode, 2, denied.stderr)
                self.assertIn("declare", denied.stderr)  # The real guard still decides.
                prompt = run_hook(self.root, provider, "UserPromptSubmit", {"session_id": "s", "prompt": "next"})
                self.assertEqual(prompt.returncode, 0, prompt.stderr)

    def test_a_broken_activity_log_never_blocks_a_declaration(self):
        (self.root / ".lean/lean/activity.py").write_text("def broken(:\n")
        declared = self.tool("claude", "Bash", command="python3 .lean/bin/lean contract declare --contract "
                                                        "'Contract: trivial (log broken)'")
        self.assertEqual(declared.returncode, 0, declared.stderr)
        self.assertEqual(self.tool("claude", "Edit", file_path="app.py").returncode, 0)

    def test_a_broken_guard_still_allows_reads_and_repairing_the_package(self):
        (self.root / ".lean/lean/guard.py").write_text("def broken(:\n")
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                self.assertEqual(self.tool(provider, "Read", file_path="x.py").returncode, 0)
                self.assertEqual(self.tool(provider, "Grep", pattern="x").returncode, 0)
                self.assertEqual(self.tool(provider, "Edit", file_path=str(self.root / ".lean/lean/guard.py")).returncode, 0)
                self.assertEqual(self.tool(provider, "Bash", command="git checkout -- .lean/lean/guard.py").returncode, 0)
                blocked = self.tool(provider, "Edit", file_path="app.py")
                self.assertEqual(blocked.returncode, 2, blocked.stderr)
                self.assertIn("cannot load", blocked.stderr)
                self.assertEqual(self.tool(provider, "Bash", command="rm -rf build").returncode, 2)

    def test_a_stop_fails_closed_when_the_gate_cannot_load(self):
        (self.root / ".lean/lean/gate.py").write_text("def broken(:\n")
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                result = run_hook(self.root, provider, "Stop", {"session_id": "s", "stop_hook_active": False})
                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)
                self.assertEqual(decision["decision"], "block")
                self.assertIn("cannot load", decision["reason"])
                self.assertIn("NOT_RUN", decision["reason"])
                # A continued Stop is released instead of looping on content that cannot load.
                again = run_hook(self.root, provider, "Stop", {"session_id": "s", "stop_hook_active": True})
                released = json.loads(again.stdout)
                self.assertNotIn("decision", released)
                self.assertIn("UNVERIFIED", released["systemMessage"])
                self.assertIn("NOT_RUN", released["systemMessage"])


if __name__ == "__main__":
    unittest.main()
