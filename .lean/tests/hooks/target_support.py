"""Shared fixture for the split target tests: real local Git submodules and boundaries."""
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, stop_refusal  # noqa: E402

DECLARE = "python3 .lean/bin/lean contract declare --contract '{}'"


MODE_ACTIONS = ("configure", "downgrade", "show", "check", "context")


def workflow_args(args):
    """4.x workflow.py arguments in v5 form: mode actions moved under `lean mode`."""
    args = [str(arg) for arg in args]
    prefix = []
    while args[:1] in (["--root"], ["--workflow-root"]):
        prefix, args = prefix + args[:2], args[2:]
    return prefix + (["mode", *args] if args and args[0] in MODE_ACTIONS else args)


class TargetFixture(unittest.TestCase):
    """Fixture and helpers only; defines no tests, so it is never collected as a test case."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean submodule ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "lean workspace"
        self.root.mkdir()
        self.env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        install(self.root, extra=(".lean/templates/tracker.md", ".lean/templates/queue-item.json", "AGENTS.md",
                                  ".lean/models.json"))
        self.env.pop("LEAN_GATE_FORCE", None)
        self.env.pop("LEAN_GATE_LOCK_FD", None)
        (self.root / ".lean/PROJECT.md").write_text("# Lean\n<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / ".lean/config.json").write_text(json.dumps({"mode": "standard", "configured": True, "execution": "direct"}))
        self.git(self.root, "init", "-q")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Lean fixture")
        self.remote = self.make_remote("application")
        self.lean = self.root / ".lean/bin/lean"

    def command(self, *args, **kwargs):
        kwargs.setdefault("cwd", self.root)
        return subprocess.run([str(a) for a in args], env=self.env, text=True, capture_output=True, **kwargs)

    def git(self, root, *args):
        result = self.command("git", "-C", root, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def make_remote(self, name):
        source = self.base / (name + " source")
        source.mkdir()
        self.git(source, "init", "-q", "--initial-branch=main")
        (source / "app.txt").write_text("application\n")
        self.git(source, "add", ".")
        self.git(source, "commit", "-qm", "Application fixture")
        remote = self.base / (name + ".git")
        self.git(source, "clone", "-q", "--bare", str(source), str(remote))
        return remote.as_uri()

    def cli(self, *args, success=True):
        result = self.command(sys.executable, self.lean, "target", *args)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def install(self, remote=None):
        return json.loads(self.cli("use", remote or self.remote, "--apply").stdout)

    def workflow(self, *args, success=True):
        result = self.command(sys.executable, self.lean, *workflow_args(args))
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def gate_file(self, context, command):
        Path(context["project_file"]).write_text("# Application\n<!-- gate:start -->\n```sh\n" + command + "\n```\n<!-- gate:end -->\n")

    def hook(self, seed=False, session=""):
        result = subprocess.run([sys.executable, str(self.lean), "hook", "claude", "session-start" if seed else "stop"],
                                input=json.dumps({"session_id": session}), env={**self.env, "CLAUDE_PROJECT_DIR": str(self.root)},
                                text=True, capture_output=True, cwd=self.root)
        return stop_refusal(result)

    def evidence(self, *args):
        result = self.command(sys.executable, self.lean, "--root", self.root, "evidence", *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def gate_entry(self, entry, *args, session=""):
        if session:
            args = (*args, "--session", session)
        if entry == "standalone":
            return self.command(sys.executable, self.lean, "target", "gate", *args)
        if entry == "claude":
            return self.hook(session=session)
        if entry == "codex":
            return stop_refusal(self.command(sys.executable, self.lean, "hook", "codex", "stop",
                                             input=json.dumps({"session_id": session})))
        return self.command(sys.executable, self.lean, "--root", self.root, "gate", "run", *args)

    def reviewed(self, contract="Contract: risk=HIGH quality=HIGH acceptance=target fixture reviewed"):
        self.evidence("record-review", "--contract", contract, "--reviewer", "independent-fixture",
                      "--verdict", "PASS", "--evidence", "target contents and controls",
                      "--state", self.evidence("state"))

    def bind(self, session, contract):
        result = self.command(sys.executable, self.lean, "--root", self.root, "hook", "claude", "pre-tool",
                              input=json.dumps({"session_id": session, "tool_name": "Bash",
                                                "tool_input": {"command": DECLARE.format(contract)}}))
        self.assertEqual(result.returncode, 0, result.stderr)
