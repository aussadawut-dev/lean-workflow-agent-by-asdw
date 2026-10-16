"""Fixture building, agent runs and transcript reading for Lean behavior evals.

A run copies the distributable template into a temporary project, adds a tiny
application, and drives a real `claude -p` session there, so the project's own
CLAUDE.md/AGENTS.md, hooks, skills and reviewer agent load as they do for users.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".lean/tests"))
from test_template import bootstrap  # noqa: E402

WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
CONTRACT = re.compile(r"^Contract: (risk=(LOW|MEDIUM|HIGH) quality=(STANDARD|HIGH|VERY_HIGH) acceptance=\S"
                      r"|trivial \()")

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


def agent_command(model, budget):
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            "--max-budget-usd", f"{budget:.2f}", "--no-session-persistence",
            # Project settings only: user-level plugins, hooks and output styles would change behavior.
            "--setting-sources", "project,local",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "Skill",
            "Bash(python3:*)", "Bash(git:*)", "Bash(bash:*)", "Bash(ls:*)", "Bash(cat:*)"]


def run_agent(root, prompt, model, budget, timeout):
    """Run one session; return (stream-json lines, exit code). The prompt goes on stdin."""
    try:
        result = subprocess.run(agent_command(model, budget), cwd=root, input=prompt, text=True,
                                capture_output=True, timeout=timeout)
        return result.stdout.splitlines(), result.returncode, result.stderr
    except subprocess.TimeoutExpired as error:
        output = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        return output.splitlines(), None, "timeout"


class Transcript:
    """Ordered events from `claude -p --output-format stream-json` (top-level session only)."""

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

    def first_write(self, path_suffix=None):
        for index, event in self.tools(*WRITE_TOOLS):
            path = str(event["input"].get("file_path", ""))
            # Compare whole path parts: "calc.py" must not match "tests/test_calc.py".
            if path_suffix is None or path == path_suffix or path.endswith("/" + path_suffix):
                return index
        return None

    def result_for(self, tool_id):
        for event in self.events:
            if event["kind"] == "tool_result" and event["id"] == tool_id:
                return event
        return None
