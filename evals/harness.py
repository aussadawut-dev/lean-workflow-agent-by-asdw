"""Fixture building, agent runs and transcript reading for Lean behavior evals.

A run copies the distributable template into a temporary project, adds a tiny
application, and drives a real `claude -p` or `codex exec` session there, so the
project's own CLAUDE.md/AGENTS.md, hooks, skills and reviewer agent load as they
do for users.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".lean/tests"))
sys.path.insert(0, str(ROOT / ".lean/scripts"))
from test_template import bootstrap  # noqa: E402
from contract_guard import parse as parse_contract  # noqa: E402

PROVIDERS = ("claude", "codex")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Codex often writes through its shell, where only the command text shows the write.
# Redirections to /dev/null and descriptor duplications such as 2>&1 are not writes.
SHELL_WRITE = re.compile(r"(?<![\d&>])>{1,2}(?!&)(?!\s*/dev/null)|\btee\b|\bsed\s+-i|\bperl\s+-\S*i"
                         r"|\bapply_patch\b|open\([^)]*['\"][wax]\+?['\"]|\.write_text\(|\b(mv|cp|touch|rm)\s")

CALC = '''"""Small calculator used by Lean behavior evals."""


def add(a, b):
    return a + b


def divide(a, b):
    # Callers rely on this retrun value being a float.
    return a / b


def mean(values):
    return sum(values) / len(values)
'''

TEST_CALC = '''import unittest

from calc import add, divide, mean


class CalcTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_divide(self):
        self.assertEqual(divide(6, 3), 2.0)

    def test_mean(self):
        self.assertEqual(mean([1, 2, 3]), 2.0)


if __name__ == "__main__":
    unittest.main()
'''

AUTH = '''"""Permission checks for the calculator service."""


def can_delete(user):
    return user.get("role") == "admin"
'''

TEST_AUTH = '''import unittest

from auth import can_delete


class AuthTests(unittest.TestCase):
    def test_admin_can_delete(self):
        self.assertTrue(can_delete({"role": "admin"}))

    def test_viewer_cannot_delete(self):
        self.assertFalse(can_delete({"role": "viewer"}))


if __name__ == "__main__":
    unittest.main()
'''

TEST_COMMAND = "python3 -m unittest discover -s tests -t ."


def project_md(gate_lines, high_risk=()):
    risk = "\n".join(f"- `{path}`: {why}" for path, why in high_risk) or "- Not defined."
    gate = "\n".join(gate_lines)
    return f"""# Project Context

## Purpose

Calculator service used by Lean behavior evals.

## Commands

- Test: `{TEST_COMMAND}`

## Quality Gate

<!-- gate:start -->
```sh
{gate}
```
<!-- gate:end -->

## High-risk areas

{risk}
"""


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=Lean Eval", "-c", "user.email=eval@example.invalid", *args],
                          cwd=root, check=True, text=True, capture_output=True).stdout


def build_fixture(root, case):
    """Template copy + application files, configured standard/direct, committed clean."""
    root = Path(root)
    bootstrap(root)
    (root / "calc.py").write_text(CALC)
    (root / "auth.py").write_text(AUTH)
    (root / "tests").mkdir()
    (root / "tests/__init__.py").write_text("")
    (root / "tests/test_calc.py").write_text(TEST_CALC)
    (root / "tests/test_auth.py").write_text(TEST_AUTH)
    (root / ".lean/PROJECT.md").write_text(project_md(case.get("gate", [TEST_COMMAND]), case.get("high_risk", ())))
    for name, text in case.get("files", {}).items():
        (root / name).write_text(text)
    subprocess.run([sys.executable, str(root / ".lean/scripts/workflow.py"), "configure", "standard",
                    "--execution", "direct"], cwd=root, check=True, capture_output=True)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "Eval fixture")
    return root


def changed_files(root):
    output = git(root, "status", "--porcelain", "--untracked-files=all")
    names = set()
    for line in output.splitlines():
        name = line[3:]
        if not name.startswith((".agent-runtime/", ".claude/.gate")) and "__pycache__" not in name:
            names.add(name.split(" -> ")[-1])
    return sorted(names)


def tests_pass(root):
    return subprocess.run(TEST_COMMAND.split(), cwd=root, capture_output=True).returncode == 0


def agent_command(model, budget, provider="claude"):
    """The session command; the prompt goes on stdin. Codex has no per-run budget flag."""
    if provider == "codex":
        return ["codex", "exec", "--json",
                # User config would change behavior (code mode, user hooks, plugins); auth still loads.
                "--ignore-user-config",
                # The fixture is a throwaway copy whose hooks were never trusted interactively.
                "--dangerously-bypass-hook-trust",
                # No --ephemeral: subagent threads (the reviewer) fail to spawn without a stored session.
                "--sandbox", "workspace-write", "--model", model, "-"]
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            # Sessions persist: the fixture's Stop hook reads the transcript to find the contract.
            "--max-budget-usd", f"{budget:.2f}",
            # Project settings only: user-level plugins, hooks and output styles would change behavior.
            "--setting-sources", "project,local",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "Skill",
            "Bash(cd:*)", "Bash(python3:*)", "Bash(git:*)", "Bash(bash:*)", "Bash(ls:*)", "Bash(cat:*)",
            "Bash(.lean/scripts/*)"]


# Raw-output signs that the harness, not the agent, broke the run.
HARNESS_FAULTS = ("transcript unreadable",)


def harness_problems(lines):
    joined = "\n".join(lines).lower()
    return [f"HARNESS: session output contains {fault!r}" for fault in HARNESS_FAULTS if fault in joined]


def run_agent(root, prompt, model, budget, timeout, provider="claude"):
    """Run one session; return (JSON event lines, exit code, stderr). The prompt goes on stdin."""
    try:
        result = subprocess.run(agent_command(model, budget, provider), cwd=root, input=prompt, text=True,
                                capture_output=True, timeout=timeout)
        return result.stdout.splitlines(), result.returncode, result.stderr
    except subprocess.TimeoutExpired as error:
        output = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        return output.splitlines(), None, "timeout"


class Transcript:
    """Ordered events from `claude -p --output-format stream-json` (top-level session only)."""

    provider = "claude"
    tokens = None

    def __init__(self, lines):
        self.events = []
        self.result = {}
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("parent_tool_use_id"):
                continue  # Subagent traffic; the reviewer's own calls are not the author's.
            kind = item.get("type")
            message = item.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if kind == "assistant" and isinstance(content, list):
                for block in filter(lambda block: isinstance(block, dict), content):
                    if block.get("type") == "text" and block.get("text", "").strip():
                        self.events.append({"kind": "text", "text": block["text"]})
                    elif block.get("type") == "tool_use":
                        self.events.append({"kind": "tool", "id": block.get("id"), "name": block.get("name"),
                                            "input": block.get("input") or {}})
            elif kind == "user" and isinstance(content, list):
                for block in filter(lambda block: isinstance(block, dict), content):
                    if block.get("type") == "tool_result":
                        body = block.get("content")
                        if isinstance(body, list):
                            body = "\n".join(part.get("text", "") for part in body if isinstance(part, dict))
                        self.events.append({"kind": "tool_result", "id": block.get("tool_use_id"),
                                            "text": body or "", "is_error": bool(block.get("is_error"))})
            elif kind == "result":
                self.result = item

    @property
    def final_text(self):
        if isinstance(self.result.get("result"), str):
            return self.result["result"]
        texts = [event["text"] for event in self.events if event["kind"] == "text"]
        return texts[-1] if texts else ""

    @property
    def cost(self):
        return self.result.get("total_cost_usd")

    def tools(self, *names):
        return [(index, event) for index, event in enumerate(self.events)
                if event["kind"] == "tool" and (not names or event["name"] in names)]

    def first_text(self):
        for index, event in enumerate(self.events):
            if event["kind"] == "text":
                return index, event["text"]
        return None, ""

    def writes(self):
        """(index, paths) per write: file tools name their path; a shell write names every path-like word."""
        for index, event in self.tools():
            if event["name"] in WRITE_TOOLS:
                yield index, [str(event["input"].get("file_path", ""))]
            elif event["name"] == "Bash" and SHELL_WRITE.search(str(event["input"].get("command", ""))):
                yield index, re.findall(r"[\w./-]+", str(event["input"]["command"]))

    def first_write(self, path_suffix=None):
        for index, paths in self.writes():
            # Compare whole path parts: "calc.py" must not match "tests/test_calc.py".
            if path_suffix is None or any(path == path_suffix or path.endswith("/" + path_suffix) for path in paths):
                return index
        return None

    def result_for(self, tool_id):
        for event in self.events:
            if event["kind"] == "tool_result" and event["id"] == tool_id:
                return event
        return None


class CodexTranscript(Transcript):
    """Ordered events from `codex exec --json`, mapped onto the Claude event shapes.

    Shell commands become `Bash` tools and file changes become `Edit`/`Write` tools
    (one per path). The stream omits `spawn_agent` calls; `attach_rollout` reads them
    from the session's stored rollout into `spawns`.
    """

    provider = "codex"

    def __init__(self, lines):  # Replaces the Claude parser; shares its queries.
        self.events = []
        self.result = {}
        self.tokens = None
        self.thread_id = None
        self.spawns = []
        self.rollout_found = False
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "thread.started":
                self.thread_id = item.get("thread_id")
            if item.get("type") == "turn.completed" and isinstance(item.get("usage"), dict):
                usage = item["usage"]
                spent = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
                self.tokens = (self.tokens or 0) + spent
            body = item.get("item")
            if item.get("type") != "item.completed" or not isinstance(body, dict):
                continue
            kind, ident = body.get("type"), body.get("id")
            if kind == "agent_message" and str(body.get("text", "")).strip():
                self.events.append({"kind": "text", "text": body["text"]})
            elif kind == "command_execution":
                self.events.append({"kind": "tool", "id": ident, "name": "Bash",
                                    "input": {"command": str(body.get("command", ""))}})
                self.events.append({"kind": "tool_result", "id": ident, "text": body.get("aggregated_output") or "",
                                    "is_error": body.get("exit_code") not in (0, None)
                                    or body.get("status") == "failed"})
            elif kind == "file_change":
                for change in filter(lambda change: isinstance(change, dict), body.get("changes") or []):
                    name = "Write" if change.get("kind") == "add" else "Edit"
                    self.events.append({"kind": "tool", "id": ident, "name": name,
                                        "input": {"file_path": str(change.get("path", ""))}})

    def attach_rollout(self, lines):
        """Record top-level `spawn_agent` calls: task name and how much of the thread the agent inherits."""
        self.rollout_found = True
        for line in lines:
            try:
                payload = json.loads(line).get("payload")
                arguments = json.loads(payload["arguments"]) if payload.get("name") == "spawn_agent" else None
            except (ValueError, AttributeError, KeyError, TypeError):
                continue
            if payload.get("type") == "function_call" and isinstance(arguments, dict):
                self.spawns.append({"task_name": str(arguments.get("task_name") or ""),
                                    "fork_turns": str(arguments.get("fork_turns") or "")})

    @property
    def final_text(self):
        texts = [event["text"] for event in self.events if event["kind"] == "text"]
        return texts[-1] if texts else ""

    @property
    def cost(self):
        return None  # Codex reports tokens, not money.


def codex_rollout(thread_id, home=None):
    """The stored rollout for a Codex thread, or None. Codex writes it under $CODEX_HOME/sessions."""
    if not thread_id:
        return None
    base = Path(home or os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    matches = sorted(base.glob(f"**/rollout-*-{thread_id}.jsonl")) if base.is_dir() else []
    return matches[0] if matches else None


def read_transcript(provider, lines, codex_home=None):
    if provider != "codex":
        return Transcript(lines)
    transcript = CodexTranscript(lines)
    rollout = codex_rollout(transcript.thread_id, codex_home)
    if rollout:
        transcript.attach_rollout(rollout.read_text().splitlines())
    return transcript
