"""Spawn planning: the three levels, waves with exclusive files, sizing and the subscription-only environment."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT  # noqa: E402
from lean import models, spawn  # noqa: E402
from lean.util import LeanError  # noqa: E402


def task(task_id, files, size="M", deps=()):
    return {"id": task_id, "files": list(files), "size": size, "deps": list(deps), "prompt": f"do {task_id}"}


FIVE = [task(f"t{n}", [f"src/f{n}.py"]) for n in range(5)]


class PlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / ".lean").mkdir()
        shutil.copy2(ROOT / ".lean/models.json", self.root / ".lean/models.json")
        self.data = models.load(self.root)

    def widths(self, planned):
        return [len(wave) for wave in planned["waves"]]

    def test_default_level_runs_one_sized_agent_at_a_time(self):
        planned = spawn.plan(self.root, FIVE, "default", "claude")
        self.assertEqual((planned["agents"], planned["concurrency"]), (1, 1))
        self.assertEqual(self.widths(planned), [1] * 5)
        model, effort = models.resolve(self.data, "claude", "M")
        self.assertTrue(all(entry["model"] == model and entry["effort"] == effort
                            for wave in planned["waves"] for entry in wave))

    def test_raised_max_agents_raises_only_the_default_level(self):
        data = json.loads((self.root / ".lean/models.json").read_text())
        data["max_agents"] = 2
        (self.root / ".lean/models.json").write_text(json.dumps(data))
        self.assertEqual(self.widths(spawn.plan(self.root, FIVE, "default", "claude")), [2, 2, 1])

    def test_max_level_spawns_one_agent_per_parallel_task(self):
        planned = spawn.plan(self.root, FIVE, "max", "codex")
        self.assertEqual((planned["agents"], self.widths(planned)), (5, [5]))
        self.assertIsNone(planned["concurrency"])

    def test_max_level_serialises_dependencies_and_shared_files(self):
        tasks = [task("api", ["src/api.py"]), task("ui", ["web/ui.js"], deps=["api"]),
                 task("docs", ["README.md"]), task("readme-badge", ["README.md"], size="S")]
        planned = spawn.plan(self.root, tasks, "max", "claude")
        self.assertEqual([[entry["id"] for entry in wave] for wave in planned["waves"]],
                         [["api", "docs"], ["ui", "readme-badge"]])
        for wave in planned["waves"]:
            owned = [path for entry in wave for path in entry["files"]]
            self.assertEqual(len(owned), len(set(owned)), "two agents in one wave own the same file")

    def test_explicit_level_uses_the_named_model_for_n_agents(self):
        planned = spawn.plan(self.root, FIVE, "explicit", "claude", model="sonnet", count=3)
        self.assertEqual((planned["agents"], self.widths(planned)), (3, [3, 2]))
        self.assertTrue(all(entry["model"] == "sonnet" for wave in planned["waves"] for entry in wave))
        self.assertEqual(planned["notes"], [])

    def test_explicit_level_reports_fewer_parallel_tasks_than_requested(self):
        chain = [task("a", ["a.py"]), task("b", ["b.py"], deps=["a"])]
        planned = spawn.plan(self.root, chain, "explicit", "claude", model="sonnet", count=3)
        self.assertEqual(planned["agents"], 1)
        self.assertIn("requested 3 agents, but only 1", planned["notes"][0])

    def test_default_level_suggests_finishing_small_tasks_in_the_session(self):
        planned = spawn.plan(self.root, [task("rename", ["x.py"], size="S"), task("feature", ["y.py"])], "default", "claude")
        self.assertIn("rename", planned["notes"][0])
        self.assertNotIn("feature", planned["notes"][0])

    def test_invalid_requests_are_refused(self):
        for args in (("explicit", "claude"), ("default", "claude", "sonnet"), ("fast", "claude"), ("max", "gemini")):
            with self.subTest(args=args), self.assertRaises(LeanError):
                spawn.plan(self.root, FIVE, *args)

    def test_task_files_are_validated(self):
        source = self.root / "tasks.json"
        bad = [{"tasks": []}, {"tasks": [task("a", [])]}, {"tasks": [task("a", ["x"]), task("a", ["y"])]},
               {"tasks": [task("a", ["x"], size="XXL")]}, {"tasks": [task("a", ["x"], deps=["missing"])]},
               {"tasks": [task("../a", ["x"])]}, {"tasks": [task("a", ["x"], deps=["b"]), task("b", ["y"], deps=["a"])]}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(LeanError):
                source.write_text(json.dumps(value))
                spawn.waves(spawn.load_tasks(source), None)
        shutil.copy2(ROOT / ".lean/templates/tasks.json", source)
        self.assertEqual([t["id"] for t in spawn.load_tasks(source)], ["api", "ui"])


class EnvironmentTests(unittest.TestCase):
    def test_metered_api_credentials_are_removed_unless_allowed(self):
        parent = {"PATH": "/bin", "ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o", "GEMINI_API_KEY": "g",
                  "LEAN_GATE_LOCK_FD": "7", "CLAUDECODE": "1", "HOME": "/h"}
        child, removed = spawn.child_environment(environment=parent)
        self.assertEqual(sorted(removed), ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"])
        self.assertEqual(child, {"PATH": "/bin", "HOME": "/h"})
        kept, removed = spawn.child_environment(allow_api_keys=True, environment=parent)
        self.assertEqual(removed, [])
        self.assertEqual(kept["OPENAI_API_KEY"], "o")
        self.assertNotIn("LEAN_GATE_LOCK_FD", kept)
        self.assertNotIn("CLAUDECODE", kept, "a Codex or agy worker must not look like Claude's shell")

    def test_commands_fill_the_provider_templates(self):
        data = json.loads((ROOT / ".lean/models.json").read_text())
        claude = spawn.command_for(data, "claude", "fix it", "claude-sonnet-5-5", "medium", 60)
        self.assertEqual(claude[:2], ["claude", "-p"])
        self.assertIn("fix it", claude)
        self.assertEqual(claude[claude.index("--model") + 1], "claude-sonnet-5-5")
        self.assertEqual(claude[claude.index("--effort") + 1], "medium")
        codex = spawn.command_for(data, "codex", "fix it", "gpt-6.1-sol", "high", 60)
        self.assertIn("model_reasoning_effort=high", codex)
        agy = spawn.command_for(data, "agy", "fix it", "gemini-4-argon-high", None, 90)
        self.assertEqual(agy[agy.index("--print-timeout") + 1], "90s")
        no_effort = spawn.command_for(data, "claude", "fix it", "m", None, 60)
        self.assertNotIn("--effort", no_effort)


if __name__ == "__main__":
    unittest.main()
