"""Opt-in trust for spawned agents: provider permission flags are added only when the run is trusted."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, install  # noqa: E402
from lean import models, spawn  # noqa: E402

STUB = '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
prompt = next(a for a in args if "TASK=" in a)
task = prompt.split("TASK=")[1].split()[0]
open(f"stub-{task}.json", "w").write(json.dumps(
    {"args": args, "keys": sorted(k for k in os.environ if k.endswith("_API_KEY"))}))
'''
PROVIDERS = ("claude", "codex", "agy")


class SpawnPermissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        install(self.root, extra=(".lean/models.json",))
        stub = self.root / "stub-cli"
        stub.write_text(STUB)
        stub.chmod(0o755)
        data = json.loads((self.root / ".lean/models.json").read_text())
        self.trusted_args = {}
        for name in PROVIDERS:
            self.trusted_args[name] = data["providers"][name].get("trusted_args")
            data["providers"][name]["command"] = str(stub)
        (self.root / ".lean/models.json").write_text(json.dumps(data))
        (self.root / ".gitignore").write_text(".agent-runtime/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")
        self.addCleanup(self.remove_worktrees)

    def remove_worktrees(self):
        for row in self.last.get("agents", []) if hasattr(self, "last") else []:
            subprocess.run(["git", "-C", str(self.root), "worktree", "remove", "--force", row["worktree"]],
                           capture_output=True)

    def run_agent(self, provider, trusted=None):
        task = {"id": "t0", "files": ["f0.py"], "size": "M", "prompt": "TASK=t0 work"}
        planned = spawn.plan(self.root, [task], provider=provider)
        shown = []
        kwargs = {} if trusted is None else {"trusted": trusted}
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret", "OPENAI_API_KEY": "secret"}):
            self.last = spawn.run(self.root, planned, timeout=20, show=shown.append, **kwargs)
        row = self.last["agents"][0]
        record = json.loads((Path(row["worktree"]) / "stub-t0.json").read_text())
        command = (Path(row["log"]).parent / "command.txt").read_text().split()
        return row, record, command, "\n".join(shown)

    def test_default_runs_never_carry_trusted_args(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                row, record, command, shown = self.run_agent(provider)
                for arg in self.trusted_args[provider] or []:
                    if not arg.startswith("-") or arg != "--permission-mode":  # Claude's default has the flag.
                        self.assertNotIn(arg, record["args"])
                        self.assertNotIn(arg, command)
                self.assertNotIn("any command", shown)
                self.assertFalse(row["trusted"])

    def test_trusted_runs_append_exactly_the_providers_trusted_args(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                expected = self.trusted_args[provider]
                self.assertIsNotNone(expected, f"{provider} needs trusted_args in models.json")
                row, record, command, shown = self.run_agent(provider, trusted=True)
                if expected:
                    self.assertEqual(record["args"][-len(expected):], expected)
                    self.assertEqual(command[-len(expected):], expected)
                self.assertIn("any command", shown)
                self.assertTrue(row["trusted"])
                self.assertEqual(record["keys"], [])  # Trust never brings back API keys.

    def test_a_trusted_claude_run_does_not_keep_the_weaker_permission_mode(self):
        _, record, _, _ = self.run_agent("claude", trusted=True)
        self.assertEqual(record["args"].count("--permission-mode"), 1)
        self.assertNotIn("acceptEdits", record["args"])

    def test_unknown_key_does_not_break_models_validation(self):
        data = json.loads((self.root / ".lean/models.json").read_text())
        self.assertEqual(models.validate(data), [])


if __name__ == "__main__":
    unittest.main()
