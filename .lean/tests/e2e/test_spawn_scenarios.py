"""Scenarios for the three spawn commands: each spawns exactly what was asked, on every provider.

A stub stands in for each provider CLI. It records the arguments it was started with and when it
ran, so the tests can check concurrency, models and effort without spending any subscription quota.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, git, install, lean  # noqa: E402

STUB = r'''#!/usr/bin/env python3
import json, os, sys, time
task = next(arg.split("TASK=")[1].split()[0] for arg in sys.argv[1:] if "TASK=" in arg)
began = time.time()
# Agents meant to run together wait here until every peer has started, so overlap never depends on how
# fast a loaded machine launches them. A single-agent run (peers 1) just sleeps long enough to be timed.
here = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), ".agent-runtime", "peers")
open(os.path.join(here, f"began-{os.path.basename(sys.argv[0])}-{task}"), "w").close()
peers = int(open(os.path.join(here, "peers.txt")).read())
mark = f"began-{os.path.basename(sys.argv[0])}-"
deadline = time.time() + 25
while time.time() < deadline and sum(name.startswith(mark) for name in os.listdir(here)) < peers:
    time.sleep(0.05)
time.sleep(1.5 if peers == 1 else 0.3)
open(f"task-{task}.txt", "w").write("done\n")
json.dump({"task": task, "args": sys.argv[1:], "began": began, "ended": time.time(),
           "provider": os.path.basename(sys.argv[0])}, open(f"stub-{task}.json", "w"))
'''


def task(task_id, size="M", deps=()):
    return {"id": task_id, "files": [f"task-{task_id}.txt"], "size": size, "deps": list(deps),
            "prompt": f"TASK={task_id} do the work"}


class SpawnScenarioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        install(self.root, extra=(".lean/models.json",))
        data = json.loads((self.root / ".lean/models.json").read_text())
        for provider in data["providers"]:
            stub = self.root / f"stub-{provider}"
            stub.write_text(STUB)
            stub.chmod(0o755)
            data["providers"][provider]["command"] = str(stub)
        (self.root / ".lean/models.json").write_text(json.dumps(data))
        self.models = data
        (self.root / ".gitignore").write_text(".agent-runtime/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")
        self.addCleanup(self.remove_worktrees)

    def remove_worktrees(self):
        for line in git(self.root, "worktree", "list", "--porcelain").splitlines():
            path = line.split(" ", 1)[1] if line.startswith("worktree ") else ""
            if path and Path(path).resolve() != self.root:
                subprocess.run(["git", "-C", str(self.root), "worktree", "remove", "--force", path], capture_output=True)

    def spawn(self, tasks, *args, provider="claude", peers=1):
        (self.root / ".agent-runtime/peers").mkdir(parents=True, exist_ok=True)
        (self.root / ".agent-runtime/peers/peers.txt").write_text(str(peers))
        path = self.root / ".agent-runtime/tasks.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"tasks": tasks}))
        planned = lean(self.root, "spawn", "plan", "--tasks", str(path), "--provider", provider, *args)
        self.assertEqual(planned.returncode, 0, planned.stderr)
        result = lean(self.root, "spawn", "run", "--tasks", str(path), "--provider", provider, "--timeout", "30",
                      *args, env=dict(os.environ, ANTHROPIC_API_KEY="k", OPENAI_API_KEY="k", GEMINI_API_KEY="k"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = json.loads((self.root / ".agent-runtime/spawn/current.json").read_text())
        records = [json.loads((Path(row["worktree"]) / f"stub-{row['id']}.json").read_text())
                   for row in status["agents"]]
        return json.loads(planned.stdout), status, records

    @staticmethod
    def most_at_once(records):
        """The largest number of agents that were running at the same moment."""
        events = sorted([(r["began"], 1) for r in records] + [(r["ended"], -1) for r in records],
                        key=lambda event: (event[0], event[1]))
        running = peak = 0
        for _, change in events:
            running += change
            peak = max(peak, running)
        return peak

    def tier(self, provider, size):
        value = self.models["providers"][provider]["tiers"][size]
        return value["model"], value["effort"]

    def arg_after(self, record, flag):
        return record["args"][record["args"].index(flag) + 1]

    # Scenario 1: no /lean-agents. One agent at a time, each sized to its task.
    def test_default_spawns_one_sized_agent_at_a_time(self):
        tasks = [task("rename", "S"), task("feature", "M"), task("redesign", "L")]
        planned, status, records = self.spawn(tasks)
        self.assertEqual((planned["level"], planned["agents"]), ("default", 1))
        self.assertIn("rename", " ".join(planned["notes"]), "an S task is suggested for the main session")
        self.assertEqual([row["status"] for row in status["agents"]], ["done"] * 3)
        self.assertEqual(self.most_at_once(records), 1, "the default level ran agents in parallel")
        logged = [json.loads(line) for line in (self.root / ".agent-runtime/activity.jsonl").read_text().splitlines()]
        spawned = [entry for entry in logged if entry["event"] == "spawn"]
        self.assertEqual([(entry["id"], entry["level"], entry["status"]) for entry in spawned],
                         [("rename", "default", "done"), ("feature", "default", "done"), ("redesign", "default", "done")])
        self.assertTrue(all(entry["seconds"] >= 1 for entry in spawned), "agent time is logged")
        for record, size in zip(records, ("S", "M", "L")):
            model, effort = self.tier("claude", size)
            self.assertEqual(self.arg_after(record, "--model"), model, record["task"])
            self.assertEqual(self.arg_after(record, "--effort"), effort, record["task"])

    # Scenario 2: /lean-agents. As many agents as tasks can run in parallel.
    def test_lean_agents_spawns_every_parallel_task_at_once(self):
        tasks = [task("api", "M"), task("ui", "S"), task("docs", "S"), task("migrate", "L")]
        planned, status, records = self.spawn(tasks, "--level", "max", peers=4)
        self.assertEqual((planned["level"], planned["agents"]), ("max", 4))
        self.assertEqual([row["status"] for row in status["agents"]], ["done"] * 4)
        self.assertEqual(self.most_at_once(records), 4, "independent tasks did not all run together")
        for record, size in zip(records, ("M", "S", "S", "L")):
            self.assertEqual(self.arg_after(record, "--model"), self.tier("claude", size)[0], record["task"])

    def test_lean_agents_respects_dependencies_and_shared_files(self):
        tasks = [task("api"), task("client", deps=["api"]), task("docs")]
        planned, status, records = self.spawn(tasks, "--level", "max", peers=2)
        self.assertEqual([[entry["id"] for entry in wave] for wave in planned["waves"]], [["api", "docs"], ["client"]])
        by_task = {record["task"]: record for record in records}
        self.assertGreaterEqual(by_task["client"]["began"], by_task["api"]["ended"], "a dependent started early")
        self.assertEqual(self.most_at_once(records), 2)

    # Scenario 3: /lean-agents <model> xN. Exactly N at a time, all on that model.
    def test_named_model_and_count_run_up_to_n_agents_at_once_on_that_model(self):
        tasks = [task(f"t{n}") for n in range(5)]
        planned, status, records = self.spawn(tasks, "--model", "sonnet", "-n", "3", peers=3)
        self.assertEqual((planned["level"], planned["agents"], planned["concurrency"]), ("explicit", 3, 3))
        self.assertEqual([row["status"] for row in status["agents"]], ["done"] * 5)
        self.assertEqual(self.most_at_once(records), 3, "the explicit count was not what ran at once")
        self.assertEqual({self.arg_after(record, "--model") for record in records}, {"sonnet"})

    def test_named_count_larger_than_the_parallel_work_spawns_fewer_and_says_why(self):
        tasks = [task("a"), task("b", deps=["a"])]
        planned, status, records = self.spawn(tasks, "--model", "sonnet", "-n", "3")
        self.assertEqual(planned["agents"], 1)
        self.assertIn("requested 3 agents, but only 1", planned["notes"][0])
        self.assertEqual(self.most_at_once(records), 1)

    # Every scenario on every provider: the provider's own model and effort flags carry the choice.
    def test_each_provider_receives_the_chosen_model_and_effort_flags(self):
        for provider in ("codex", "agy"):
            with self.subTest(provider=provider):
                planned, status, records = self.spawn([task("x", "L"), task("y", "S")], "--level", "max",
                                                      provider=provider, peers=2)
                self.assertEqual(planned["provider"], provider)
                self.assertEqual(self.most_at_once(records), 2)
                for record, size in zip(records, ("L", "S")):
                    model, effort = self.tier(provider, size)
                    if provider == "codex":
                        self.assertEqual(record["args"][0], "exec")
                        self.assertEqual(self.arg_after(record, "-m"), model)
                        self.assertIn(f"model_reasoning_effort={effort}", record["args"])
                    else:
                        self.assertEqual(self.arg_after(record, "--model"), model)
                        self.assertEqual(self.arg_after(record, "--print-timeout"), "30s")
                        self.assertNotIn("--effort", record["args"])
                self.remove_worktrees()
        planned, status, records = self.spawn([task("z")], "--model", "gpt-6-luna", "-n", "1", provider="codex")
        self.assertEqual(self.arg_after(records[0], "-m"), "gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
