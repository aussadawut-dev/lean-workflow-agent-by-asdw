"""`lean spawn run` with a stub provider CLI: worktrees, per-agent bars, API keys removed, timeouts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, git, install, lean  # noqa: E402

# The stub records what it was given, edits its own file, reports progress and optionally sleeps.
STUB = '''#!/usr/bin/env python3
import json, os, subprocess, sys, time
args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
task = prompt.split("TASK=")[1].split()[0]
record = {"args": args, "cwd": os.getcwd(), "keys": sorted(k for k in os.environ if k.endswith("_API_KEY")),
          "lock": "LEAN_GATE_LOCK_FD" in os.environ}
open(f"stub-{task}.json", "w").write(json.dumps(record))
subprocess.run([sys.executable, ".lean/bin/lean", "progress", "set", "test", "--done", "1", "--total", "2"],
               capture_output=True)
for line in prompt.splitlines():
    if line.startswith("WRITE "):  # Produce a file a dependent task can read.
        name, _, text = line[6:].partition("=")
        open(name, "w").write(text)
    if line.startswith("READ "):  # Record whether a dependency's file is present.
        name = line[5:]
        record["saw"] = open(name).read() if os.path.exists(name) else None
        open(f"stub-{task}.json", "w").write(json.dumps(record))
if "BACKGROUND" in prompt:  # Exit cleanly but leave a child running.
    child = subprocess.Popen(["sleep", "60"])
    open(f"grandchild-{task}.pid", "w").write(str(child.pid))
if "SLEEP" in prompt:
    child = subprocess.Popen(["sleep", "60"])  # A grandchild the runner must also stop.
    open(f"grandchild-{task}.pid", "w").write(str(child.pid))
    time.sleep(30)
if "DENIED" in prompt:  # A provider that refused a tool in headless mode: no edit, exit 0.
    os.remove(f"stub-{task}.json")
    print(json.dumps({"status": "SUCCESS", "response": "", "denied_actions": [{"display_name": "RunCommand"}]}))
sys.exit(3 if "FAIL" in prompt else 0)
'''


class SpawnRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        install(self.root, extra=(".lean/models.json",))
        stub = self.root / "stub-cli"
        stub.write_text(STUB)
        stub.chmod(0o755)
        data = json.loads((self.root / ".lean/models.json").read_text())
        data["providers"]["claude"]["command"] = str(stub)
        (self.root / ".lean/models.json").write_text(json.dumps(data))
        (self.root / ".gitignore").write_text(".agent-runtime/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")
        self.addCleanup(self.remove_worktrees)

    def remove_worktrees(self):
        for line in git(self.root, "worktree", "list", "--porcelain").splitlines():
            path = line.split(" ", 1)[1] if line.startswith("worktree ") else ""
            if path and Path(path).resolve() != self.root:
                subprocess.run(["git", "-C", str(self.root), "worktree", "remove", "--force", path], capture_output=True)

    def tasks(self, *prompts, deps=None):
        path = self.root / ".agent-runtime/tasks.json"
        path.parent.mkdir(exist_ok=True)
        tasks = [{"id": f"t{n}", "files": [f"f{n}.py"], "size": "M", "prompt": f"TASK=t{n} {prompt}",
                  "deps": (deps or {}).get(f"t{n}", [])}
                 for n, prompt in enumerate(prompts)]
        path.write_text(json.dumps({"tasks": tasks}))
        return str(path)

    def run_spawn(self, *args, env=None):
        environment = dict(os.environ, ANTHROPIC_API_KEY="secret", OPENAI_API_KEY="secret", **(env or {}))
        return lean(self.root, "spawn", "run", "--provider", "claude", *args, env=environment)

    def stub_record(self, row):
        return json.loads((Path(row["worktree"]) / f"stub-{row['id']}.json").read_text())

    def status(self):
        return json.loads((self.root / ".agent-runtime/spawn/current.json").read_text())

    def test_trust_agents_flag_is_opt_in_and_warns(self):
        default = self.run_spawn("--tasks", self.tasks("work"), "--timeout", "20")
        self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
        self.assertNotIn("bypassPermissions", self.stub_record(self.status()["agents"][0])["args"])
        self.assertFalse(self.status()["agents"][0]["trusted"])
        self.remove_worktrees()
        trusted = self.run_spawn("--tasks", self.tasks("work"), "--timeout", "20", "--trust-agents")
        self.assertEqual(trusted.returncode, 0, trusted.stdout + trusted.stderr)
        row = self.status()["agents"][0]
        self.assertTrue(row["trusted"])
        self.assertEqual(self.stub_record(row)["args"][-2:], ["--permission-mode", "bypassPermissions"])
        self.assertIn("TRUSTED run", trusted.stdout + trusted.stderr)

    def test_parallel_agents_run_in_their_own_worktrees_without_api_keys(self):
        result = self.run_spawn("--tasks", self.tasks("work", "work"), "--level", "max", "--timeout", "20")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("removed metered API credentials", result.stderr)
        self.assertIn("ANTHROPIC_API_KEY", result.stderr)
        self.assertNotIn("secret", result.stdout + result.stderr)
        rows = self.status()["agents"]
        self.assertEqual([row["status"] for row in rows], ["done", "done"])
        worktrees = {row["worktree"] for row in rows}
        self.assertEqual(len(worktrees), 2)
        for row in rows:
            record = self.stub_record(row)
            self.assertEqual(Path(record["cwd"]).resolve(), Path(row["worktree"]).resolve())
            self.assertEqual(record["keys"], [])
            self.assertFalse(record["lock"])
            model = record["args"][record["args"].index("--model") + 1]
            self.assertEqual(model, row["model"])
            self.assertEqual(row["progress"]["phase"], "test")  # Read from the agent's own worktree.
            command = (Path(row["log"]).parent / "command.txt").read_text()
            self.assertIn("<prompt>", command)
            self.assertIn(row["model"], command)
        self.assertIn("█" * 20 + " 100% t0", result.stderr)  # One bar per agent.
        watch = lean(self.root, "watch", "--once").stdout
        self.assertIn("agents:", watch)
        self.assertIn("t1 [claude/", watch)
        cleaned = lean(self.root, "spawn", "clean", self.status()["run"])
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        self.assertFalse(any(Path(path).exists() for path in worktrees))
        self.assertNotIn("lean-spawn/", git(self.root, "branch", "--list"))

    def test_the_explicit_level_puts_every_agent_on_the_named_model(self):
        result = self.run_spawn("--tasks", self.tasks("work", "work", "work"), "--model", "stub-model", "-n", "2",
                                "--timeout", "20")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = self.status()["agents"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(self.stub_record(row)["args"][self.stub_record(row)["args"].index("--model") + 1]
                            == "stub-model" for row in rows))

    def test_api_keys_are_kept_only_when_allowed(self):
        result = self.run_spawn("--tasks", self.tasks("work"), "--allow-api-keys", "--timeout", "20")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = self.stub_record(self.status()["agents"][0])
        self.assertEqual(record["keys"], ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"])

    @staticmethod
    def gone(pid, wait=10):
        """True once the process has exited; a loaded machine may take a moment to reap it."""
        end = time.monotonic() + wait
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.1)
        return False

    def test_failures_and_timeouts_are_reported_and_fail_the_run(self):
        result = self.run_spawn("--tasks", self.tasks("FAIL", "SLEEP"), "--level", "max", "--timeout", "6")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        rows = self.status()["agents"]
        self.assertEqual([row["status"] for row in rows], ["failed", "timeout"])
        pid = int((Path(rows[1]["worktree"]) / "grandchild-t1.pid").read_text())
        self.assertTrue(self.gone(pid), "a timed-out agent's own children must be stopped too")

    def test_an_agent_that_exits_cleanly_leaves_no_background_child(self):
        result = self.run_spawn("--tasks", self.tasks("BACKGROUND"), "--timeout", "20")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = self.status()["agents"][0]
        pid = int((Path(row["worktree"]) / "grandchild-t0.pid").read_text())
        self.assertTrue(self.gone(pid), "a clean exit left a background child running")

    def test_dependents_start_from_their_dependencies_results(self):
        tasks = self.tasks("\nWRITE f0.py=made by t0", "\nREAD f0.py", deps={"t1": ["t0"]})
        result = self.run_spawn("--tasks", tasks, "--level", "max", "--timeout", "20")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = self.status()["agents"]
        self.assertEqual(self.stub_record(rows[1])["saw"], "made by t0")

    def test_dependents_of_an_unsuccessful_task_are_skipped(self):
        tasks = self.tasks("FAIL", "\nREAD f0.py", "work", deps={"t1": ["t0"]})
        result = self.run_spawn("--tasks", tasks, "--level", "max", "--timeout", "20")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        rows = {row["id"]: row for row in self.status()["agents"]}
        self.assertEqual((rows["t0"]["status"], rows["t1"]["status"], rows["t2"]["status"]),
                         ("failed", "skipped", "done"))
        self.assertIn("t0", rows["t1"]["note"])
        self.assertFalse(Path(rows["t1"]["worktree"]).exists(), "a skipped task never starts")

    def test_an_agent_that_changed_nothing_is_not_done_and_denied_tools_are_named(self):
        result = self.run_spawn("--tasks", self.tasks("DENIED"), "--timeout", "20")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        row = self.status()["agents"][0]
        self.assertEqual(row["status"], "no-changes")
        self.assertIn("RunCommand", row["note"])
        self.assertIn("denied tools it needed in headless mode: RunCommand", result.stdout)
        self.assertNotIn("100% t0", result.stderr)

    def test_an_uncommitted_tree_is_refused_unless_allowed(self):
        (self.root / "dirty.txt").write_text("x\n")
        refused = self.run_spawn("--tasks", self.tasks("work"))
        self.assertEqual(refused.returncode, 2)
        self.assertIn("uncommitted changes", refused.stderr)
        allowed = self.run_spawn("--tasks", self.tasks("work"), "--allow-dirty", "--timeout", "20")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)


if __name__ == "__main__":
    unittest.main()
